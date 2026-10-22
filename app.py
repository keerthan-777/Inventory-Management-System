from dotenv import load_dotenv
load_dotenv()
from flask_wtf.csrf import CSRFProtect
from io import BytesIO
from flask import send_file
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from flask import (
    Flask, jsonify, request, render_template,
    redirect, url_for, session, flash
)
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.security import generate_password_hash, check_password_hash
import math
import os
from models import db, Product, StockMovement, User


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "dev-only-change-this-secret-key"
)
csrf = CSRFProtect(app)

# --------------------------------------------------
# 1. Flask and database configuration
# --------------------------------------------------

os.makedirs(app.instance_path, exist_ok=True)

app.config["SQLALCHEMY_DATABASE_URI"] = (
    "sqlite:///" + os.path.join(app.instance_path, "inventory.db")
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

with app.app_context():
    db.create_all()
    
# --------------------------------------------------
# User authentication protection
# --------------------------------------------------


@app.before_request
def require_login():
    public_endpoints = {
        "login",
        "register",
        "static",
        "health_check",
    }


    if request.endpoint in public_endpoints:
        return None

    if session.get("user_id") is None:
        if request.path.startswith("/api/"):
            return jsonify({"error": "Please log in first"}), 401

        return redirect(url_for("login"))

    return None


# --------------------------------------------------
# User registration, login, and logout
# --------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not username or not email or not password:
            flash("All fields are required.", "error")
            return render_template("register.html")

        if len(username) > 80:
            flash("Username must be at most 80 characters.", "error")
            return render_template("register.html")

        if len(email) > 120 or "@" not in email:
            flash("Please enter a valid email address.", "error")
            return render_template("register.html")

        if len(password) < 8:
            flash("Password must contain at least 8 characters.", "error")
            return render_template("register.html")

        existing_user = User.query.filter(
            db.or_(
                User.username.ilike(username),
                User.email == email
            )
        ).first()

        if existing_user:
            flash("Username or email is already registered.", "error")
            return render_template("register.html")

        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password)
        )

        try:
            db.session.add(user)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Username or email is already registered.", "error")
            return render_template("register.html")
        except SQLAlchemyError:
            db.session.rollback()
            app.logger.exception("Registration database error")
            flash("Unable to create your account. Please try again.", "error")
            return render_template("register.html")

        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username_or_email = request.form.get(
            "username_or_email", ""
        ).strip()
        password = request.form.get("password", "")

        user = User.query.filter(
            db.or_(
                User.username.ilike(username_or_email),
                User.email == username_or_email.lower()
            )
        ).first()

        if user and check_password_hash(user.password_hash, password):
            session.clear()
            session["user_id"] = user.id
            session["username"] = user.username
            return redirect(url_for("dashboard"))

        flash("Invalid username/email or password.", "error")

    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))





# --------------------------------------------------
# 2. Shared validation helpers
# --------------------------------------------------

REQUIRED_FIELDS = {
    "name",
    "sku",
    "category",
    "quantity",
    "purchase_price",
    "selling_price",
}

ALLOWED_FIELDS = REQUIRED_FIELDS | {"reorder_level"}

TEXT_FIELDS = {"name", "sku", "category"}
INTEGER_FIELDS = {"quantity", "reorder_level"}
PRICE_FIELDS = {"purchase_price", "selling_price"}


def error_response(message, status_code, **extra):
    """Return a consistent JSON error response."""
    return jsonify({"error": message, **extra}), status_code


def validate_product_data(data, partial=False):
    """
    Validate product input.

    partial=False: required fields must be provided.
    partial=True: validate only the fields being updated.

    Returns (cleaned_data, error_message).
    """
    if not isinstance(data, dict):
        return None, "A JSON object is required"

    if not data:
        return None, "Provide product data"

    unknown_fields = set(data.keys()) - ALLOWED_FIELDS

    if unknown_fields:
        return None, (
            "Unknown fields: " + ", ".join(sorted(unknown_fields))
        )

    if not partial:
        missing_fields = REQUIRED_FIELDS - set(data.keys())

        if missing_fields:
            return None, (
                "Missing required fields: "
                + ", ".join(sorted(missing_fields))
            )

    cleaned = {}

    # Validate text fields
    for field in TEXT_FIELDS:
        if field not in data:
            continue

        value = data[field]

        if not isinstance(value, str) or not value.strip():
            return None, f"{field} must be a non-empty string"

        value = value.strip()

        max_lengths = {
            "name": 100,
            "sku": 50,
            "category": 50,
        }

        if len(value) > max_lengths[field]:
            return None, (
                f"{field} must not exceed "
                f"{max_lengths[field]} characters"
            )

        cleaned[field] = value

    # Validate integer fields
    for field in INTEGER_FIELDS:
        if field not in data:
            continue

        value = data[field]

        if isinstance(value, bool):
            return None, f"{field} must be a non-negative integer"

        try:
            if isinstance(value, int):
                number = value
            elif isinstance(value, float):
                if not math.isfinite(value) or not value.is_integer():
                    return None, (
                        f"{field} must be a non-negative integer"
                    )
                number = int(value)
            elif isinstance(value, str) and value.strip():
                number = int(value.strip())
            else:
                return None, (
                    f"{field} must be a non-negative integer"
                )
        except (ValueError, TypeError, OverflowError):
            return None, f"{field} must be a non-negative integer"

        if number < 0:
            return None, f"{field} cannot be negative"

        cleaned[field] = number

    # Validate prices
    for field in PRICE_FIELDS:
        if field not in data:
            continue

        value = data[field]

        if isinstance(value, bool):
            return None, f"{field} must be a valid non-negative number"

        try:
            number = float(value)
        except (ValueError, TypeError, OverflowError):
            return None, f"{field} must be a valid non-negative number"

        if not math.isfinite(number) or number < 0:
            return None, f"{field} must be a valid non-negative number"

        cleaned[field] = number

    # Default reorder level for new products
    if not partial and "reorder_level" not in cleaned:
        cleaned["reorder_level"] = 5

    return cleaned, None


def product_to_dict(product):
    """Convert a Product model to a JSON-friendly dictionary."""
    return {
        "id": product.id,
        "name": product.name,
        "sku": product.sku,
        "category": product.category,
        "quantity": product.quantity,
        "purchase_price": product.purchase_price,
        "selling_price": product.selling_price,
        "reorder_level": product.reorder_level,
    }


# --------------------------------------------------
# 3. Error handlers
# --------------------------------------------------

@app.errorhandler(404)
def handle_not_found(error):
    if request.path.startswith("/api/"):
        return error_response("API endpoint or resource not found", 404)

    return error


@app.errorhandler(405)
def handle_method_not_allowed(error):
    if request.path.startswith("/api/"):
        return error_response("HTTP method not allowed for this endpoint", 405)

    return error


@app.errorhandler(500)
def handle_internal_server_error(error):
    # Do not expose internal exception details to clients.
    if request.path.startswith("/api/"):
        db.session.rollback()
        return error_response("An unexpected server error occurred", 500)

    return error


# --------------------------------------------------
# 4. Home and dashboard routes
# --------------------------------------------------

@app.route("/")
def home():
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
def dashboard():
    return render_template("index.html")


@app.route("/api/health")
def health_check():
    return jsonify({"status": "healthy"}), 200


# --------------------------------------------------
# 5. GET all products / search / category filter
# --------------------------------------------------

@app.route("/api/products", methods=["GET"])
def get_products():
    query = Product.query

    search = request.args.get("search", "").strip()

    if search:
        query = query.filter(
            db.or_(
                Product.name.ilike(f"%{search}%"),
                Product.sku.ilike(f"%{search}%")
            )
        )

    category = request.args.get("category", "").strip()

    if category:
        query = query.filter(
            Product.category.ilike(category)
        )

    products = query.order_by(Product.id).all()

    return jsonify([
        product_to_dict(product)
        for product in products
    ]), 200


# --------------------------------------------------
# 6. POST - Add a new product
# --------------------------------------------------

@app.route("/api/products", methods=["POST"])
def add_product():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return error_response("A valid JSON object is required", 400)

    cleaned, validation_error = validate_product_data(data)

    if validation_error:
        return error_response(validation_error, 400)

    # Check for an existing SKU
    existing_product = Product.query.filter_by(
        sku=cleaned["sku"]
    ).first()

    if existing_product:
        return error_response(
            "A product with this SKU already exists",
            409
        )

    product = Product(**cleaned)

    try:
        db.session.add(product)
        db.session.commit()

    except IntegrityError:
        db.session.rollback()

        # Also handles a duplicate SKU inserted concurrently.
        return error_response(
            "A product with this SKU already exists",
            409
        )

    except SQLAlchemyError:
        db.session.rollback()
        app.logger.exception("Database error while adding product")

        return error_response(
            "Unable to save the product due to a database error",
            500
        )

    return jsonify({
        "message": "Product added successfully",
        "product": product_to_dict(product)
    }), 201


# --------------------------------------------------
# 7. GET one product
# --------------------------------------------------

@app.route("/api/products/<int:product_id>", methods=["GET"])
def get_product(product_id):
    product = db.session.get(Product, product_id)

    if product is None:
        return error_response("Product not found", 404)

    return jsonify(product_to_dict(product)), 200


# --------------------------------------------------
# 8. PUT - Update a product
# --------------------------------------------------

@app.route("/api/products/<int:product_id>", methods=["PUT"])
def update_product(product_id):
    product = db.session.get(Product, product_id)

    if product is None:
        return error_response("Product not found", 404)

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return error_response("A valid JSON object is required", 400)

    cleaned, validation_error = validate_product_data(
        data,
        partial=True
    )

    if validation_error:
        return error_response(validation_error, 400)

    # Check SKU uniqueness only when SKU is being changed.
    if "sku" in cleaned:
        existing_product = Product.query.filter_by(
            sku=cleaned["sku"]
        ).first()

        if (
            existing_product is not None
            and existing_product.id != product.id
        ):
            return error_response(
                "A product with this SKU already exists",
                409
            )

    # Apply validated changes.
    for field, value in cleaned.items():
        setattr(product, field, value)

    try:
        db.session.commit()

    except IntegrityError:
        db.session.rollback()
        return error_response(
            "The update conflicts with an existing product, such as a duplicate SKU",
            409
        )

    except SQLAlchemyError:
        db.session.rollback()
        app.logger.exception("Database error while updating product")

        return error_response(
            "Unable to update the product due to a database error",
            500
        )

    return jsonify({
        "message": "Product updated successfully",
        "product": product_to_dict(product)
    }), 200


# --------------------------------------------------
# 9. DELETE - Remove a product
# --------------------------------------------------

@app.route("/api/products/<int:product_id>", methods=["DELETE"])
def delete_product(product_id):
    product = db.session.get(Product, product_id)

    if product is None:
        return error_response("Product not found", 404)

    try:
        db.session.delete(product)
        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()
        app.logger.exception("Database error while deleting product")

        return error_response(
            "Unable to delete the product due to a database error",
            500
        )

    return jsonify({
        "message": "Product deleted successfully",
        "id": product_id
    }), 200


# --------------------------------------------------
# 10. GET low-stock products
# --------------------------------------------------

@app.route("/api/products/low-stock", methods=["GET"])
def get_low_stock_products():
    products = Product.query.filter(
        Product.quantity <= Product.reorder_level
    ).order_by(Product.id).all()

    return jsonify({
        "count": len(products),
        "products": [
            {
                "id": product.id,
                "name": product.name,
                "sku": product.sku,
                "category": product.category,
                "quantity": product.quantity,
                "reorder_level": product.reorder_level,
            }
            for product in products
        ]
    }), 200


# --------------------------------------------------
# 11. GET inventory financial summary
# --------------------------------------------------

@app.route("/api/inventory-summary", methods=["GET"])
def inventory_summary():
    products = Product.query.all()

    total_inventory_cost = sum(
        product.quantity * product.purchase_price
        for product in products
    )

    potential_sales_value = sum(
        product.quantity * product.selling_price
        for product in products
    )

    potential_profit = (
        potential_sales_value - total_inventory_cost
    )

    return jsonify({
        "total_inventory_cost": round(total_inventory_cost, 2),
        "potential_sales_value": round(potential_sales_value, 2),
        "potential_profit": round(potential_profit, 2)
    }), 200


@app.route("/api/stock-movements", methods=["POST"])
def create_stock_movement():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "A JSON object is required"}), 400

    product_id = data.get("product_id")
    movement_type = data.get("movement_type")
    quantity = data.get("quantity")
    reason = data.get("reason", "")

    # Validate product ID
    if (
        isinstance(product_id, bool)
        or not isinstance(product_id, int)
        or product_id <= 0
    ):
        return jsonify({"error": "A valid product_id is required"}), 400

    # Validate movement type
    if movement_type not in ("in", "out"):
        return jsonify({
            "error": "movement_type must be 'in' or 'out'"
        }), 400

    # Validate quantity
    if (
        isinstance(quantity, bool)
        or not isinstance(quantity, int)
        or quantity <= 0
    ):
        return jsonify({
            "error": "Quantity must be a positive integer"
        }), 400

    # Validate reason
    if not isinstance(reason, str) or len(reason.strip()) > 200:
        return jsonify({
            "error": "Reason must be text of at most 200 characters"
        }), 400

    product = db.session.get(Product, product_id)

    if product is None:
        return jsonify({"error": "Product not found"}), 404

    # Calculate new stock quantity
    if movement_type == "out" and product.quantity < quantity:
        return jsonify({
            "error": "Insufficient stock",
            "available_quantity": product.quantity
        }), 400

    try:
        if movement_type == "in":
            product.quantity += quantity
        else:
            product.quantity -= quantity

        movement = StockMovement(
            product_id=product.id,
            movement_type=movement_type,
            quantity=quantity,
            reason=reason.strip() or (
                "Stock received" if movement_type == "in"
                else "Stock issued"
            )
        )

        db.session.add(movement)
        db.session.commit()

        return jsonify({
            "message": "Stock movement recorded successfully",
            "movement": {
                "id": movement.id,
                "product_id": product.id,
                "product_name": product.name,
                "movement_type": movement.movement_type,
                "quantity": movement.quantity,
                "reason": movement.reason,
                "created_at": movement.created_at.isoformat(),
                "current_stock": product.quantity
            }
        }), 201

    except SQLAlchemyError:
        db.session.rollback()
        app.logger.exception("Failed to record stock movement")
        return jsonify({
            "error": "Database error while recording stock movement"
        }), 500


@app.route("/api/stock-movements", methods=["GET"])
def get_stock_movements():
    movements = (
        StockMovement.query
        .order_by(StockMovement.created_at.desc(),
                  StockMovement.id.desc())
        .all()
    )

    return jsonify([
        {
            "id": movement.id,
            "product_id": movement.product_id,
            "product_name": movement.product.name,
            "movement_type": movement.movement_type,
            "quantity": movement.quantity,
            "reason": movement.reason,
            "created_at": movement.created_at.isoformat()
        }
        for movement in movements
    ]), 200

@app.route("/reports/export.xlsx")
def export_inventory_report():
    products = Product.query.order_by(Product.name).all()
    movements = (
        StockMovement.query
        .order_by(StockMovement.created_at.desc())
        .all()
    )

    workbook = Workbook()

    # 1. Inventory worksheet
    inventory = workbook.active
    inventory.title = "Inventory"

    inventory.append([
        "ID", "Product Name", "SKU", "Category", "Quantity",
        "Purchase Price (INR)", "Selling Price (INR)",
        "Reorder Level", "Inventory Cost (INR)",
        "Potential Sales (INR)", "Potential Profit (INR)", "Stock Status"
    ])

    for product in products:
        quantity = product.quantity
        cost = quantity * product.purchase_price
        sales = quantity * product.selling_price
        profit = sales - cost
        status = (
            "Low Stock"
            if quantity <= product.reorder_level
            else "In Stock"
        )

        inventory.append([
            product.id, product.name, product.sku, product.category,
            quantity, product.purchase_price, product.selling_price,
            product.reorder_level, cost, sales, profit, status
        ])

    # 2. Low-stock worksheet
    low_stock = workbook.create_sheet("Low Stock")
    low_stock.append([
        "ID", "Product Name", "SKU", "Category",
        "Quantity", "Reorder Level"
    ])

    for product in products:
        if product.quantity <= product.reorder_level:
            low_stock.append([
                product.id, product.name, product.sku, product.category,
                product.quantity, product.reorder_level
            ])

    # 3. Stock-movement history worksheet
    history = workbook.create_sheet("Stock Movements")
    history.append([
        "Movement ID", "Date & Time", "Product", "Movement Type",
        "Quantity", "Reason"
    ])

    for movement in movements:
        history.append([
            movement.id,
            movement.created_at,
            movement.product.name if movement.product else "Unknown",
            movement.movement_type,
            movement.quantity,
            movement.reason
        ])

    # 4. Summary worksheet
    summary = workbook.create_sheet("Summary")

    total_units = sum(p.quantity for p in products)
    total_cost = sum(p.quantity * p.purchase_price for p in products)
    total_sales = sum(p.quantity * p.selling_price for p in products)
    total_profit = total_sales - total_cost
    low_count = sum(
        1 for p in products if p.quantity <= p.reorder_level
    )

    summary.append(["Inventory Summary", "Value"])
    summary.append(["Total Products", len(products)])
    summary.append(["Total Units in Stock", total_units])
    summary.append(["Low-Stock Products", low_count])
    summary.append(["Total Inventory Cost (INR)", total_cost])
    summary.append(["Potential Sales Value (INR)", total_sales])
    summary.append(["Potential Profit (INR)", total_profit])

    # Format worksheet headers and columns
    for sheet in workbook.worksheets:
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions

        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill(
                fill_type="solid",
                fgColor="1D4ED8"
            )
            cell.alignment = Alignment(
                horizontal="center",
                vertical="center"
            )

        for column_cells in sheet.columns:
            column_letter = get_column_letter(column_cells[0].column)
            max_length = max(
                len(str(cell.value)) if cell.value is not None else 0
                for cell in column_cells
            )
            sheet.column_dimensions[column_letter].width = min(
                max(max_length + 2, 12), 35
            )

    # Format monetary columns in the Inventory worksheet
    for row in inventory.iter_rows(min_row=2, min_col=6, max_col=11):
        for cell in row:
            cell.number_format = '₹#,##0.00'

    # Format monetary values in the Summary worksheet
    for row in range(5, 8):
        summary.cell(row=row, column=2).number_format = '₹#,##0.00'

    # Format movement timestamps in Excel
    for row in range(2, history.max_row + 1):
        history.cell(row=row, column=2).number_format = "yyyy-mm-dd hh:mm"

    output = BytesIO()
    workbook.save(output)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="inventory_report.xlsx",
        mimetype=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )


# --------------------------------------------------
# 12. Start Flask
# --------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True)
