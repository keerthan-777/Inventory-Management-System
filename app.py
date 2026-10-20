
from flask import Flask, jsonify, request, render_template
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
import math
import os
from models import db, Product, StockMovement
from models import db, Product

app = Flask(__name__)

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
    return jsonify({
        "message": "Inventory Management System API is running!"
    }), 200


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


from sqlalchemy.exc import SQLAlchemyError


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

# --------------------------------------------------
# 12. Start Flask
# --------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True)
