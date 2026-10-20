# Inventory-Management-System
_Add and manage products, Track stock, Low-stock alerts, Dashboard and reports_

**1. What will your project do?**

Imagine a shop that sells mobile phones, laptops, accessories, and other products. The owner needs to know which products are available, how much stock remains, and which products need restocking. 

**Your application will allow the owner to:**
------------------------------------------
Add and manage products

Add a product name, SKU, category, purchase price, selling price, and quantity.

Track stock

Increase or decrease quantities when goods arrive or are sold.

Low-stock alerts

Show products whose quantities have fallen below a defined threshold.

Dashboard and reports

Display total products, total units, stock value, and low-stock products.

**2. Technologies you'll use**
Technology	What you'll learn
Python	Backend programming and business logic
Flask	Routes, request handling, and API development
REST API	GET, POST, PUT, PATCH, and DELETE
SQLAlchemy	Database models and queries
SQLite	Local database development
PostgreSQL	Production database
HTML, CSS, JavaScript	Frontend and API integration
Postman	API testing
Git and GitHub	Version control
Render	Online deployment

**3. How the complete application works**

Frontend — HTML, CSS, JavaScript

Product forms, stock tables, dashboard

REST API

JSON requests and HTTP responses

Flask backend

Validation, stock calculations, business rules

PostgreSQL database

Products and stock movement records


For example, when a shop receives 20 new keyboards:
1. The user enters the received quantity in the frontend.
2. JavaScript sends a request to the Flask API.
3. Flask validates the quantity and updates the database.
4. The stock movement is recorded.
5. The frontend refreshes and shows the new quantity.
This is valuable practice because you learn both API development and how to implement real business rules.

**4. REST API endpoints you'll build**

Method	Endpoint	Purpose
GET	/api/products	List all products
GET	/api/products/1	View a specific product
POST	/api/products	Add a product
PUT	/api/products/1	Update product details
DELETE	/api/products/1	Delete a product, subject to business rules
POST	/api/products/1/stock	Record stock received or issued
GET	/api/dashboard	Retrieve dashboard statistics
GET	/api/stock-movements	View stock history
You can also implement search, category filtering, pagination, and low-stock filtering.

**6. Database design**
Instead of keeping everything in one table, create separate tables for the main entities.
 Products
id, name, SKU, category_id, purchase_price, selling_price, quantity, reorder_level

 Categories
id, name

 Stock Movements
id, product_id, movement_type, quantity, created_at, notes

Relationship: one category can contain many products, and one product can have many stock movement records.

This structure gives you practice with primary keys, foreign keys, relationships, SQL joins, and database transactions.
**6. Build it in stages   **   

1. Stage 1: Set up Flask and create a basic API.
2. Stage 2: Connect SQLite using SQLAlchemy and implement product CRUD operations.
3. Stage 3: Add categories, stock updates, validation, and stock movement history.
4. Stage 4: Build the frontend and connect it using JavaScript fetch().
5. Stage 5: Test APIs using Postman and handle errors properly.
6. Stage 6: Push the code to GitHub and deploy Flask on Render with PostgreSQL.
7. Stage 7: Test the live website, database persistence, and stock calculations.
7. Features to add later
Once the basic version works, you can add user login and admin roles, supplier management, purchase orders, sales records, CSV exports, and charts. Avoid adding everything at once; a complete, working core application is a stronger starting point.
