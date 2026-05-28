from flask import Blueprint, request, jsonify
from app.models.product import Product
from app import db
from flask_cors import CORS


product_bp = Blueprint("product_bp", __name__)
CORS(product_bp)


# Validation function
def validate_product_data(data):
    errors = []

    if not data.get('name'):
        errors.append('Product name is required')

    try:
        sell_price = float(data.get('sellPrice', 0))
        if sell_price < 0:
            errors.append('Rate cannot be negative')
    except (TypeError, ValueError):
        errors.append('Invalid rate')

    try:
        quantity = int(data.get('quantity', 0))
        if quantity < 0:
            errors.append('Quantity cannot be negative')
    except (TypeError, ValueError):
        errors.append('Invalid quantity')

    return errors


# ------------------ CREATE PRODUCT ------------------
@product_bp.route("/products", methods=["POST"])
def create_product():
    try:
        data = request.get_json()

        errors = validate_product_data(data)
        if errors:
            return jsonify({"errors": errors}), 400

        product = Product(
            name=data.get("name", "").strip(),
            model=data.get("model", "").strip(),
            type=data.get("type", "").strip(),
            watts=float(data.get("watts", 0)) if data.get("watts") else None,
            quantity=int(data.get("quantity", 0)),
            buy_price=float(data.get("buyPrice", 0)),
            sell_price=float(data.get("sellPrice", 0)),
            category=data.get("category", "").strip(),
        )

        db.session.add(product)
        db.session.commit()

        return jsonify(product.to_dict()), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400


# ------------------ GET ALL PRODUCTS ------------------
@product_bp.route("/products", methods=["GET"])
def get_products():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)

        pagination = Product.query.paginate(page=page, per_page=per_page, error_out=False)

        return jsonify({
            'items': [p.to_dict() for p in pagination.items],
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page,
            'per_page': per_page
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ------------------ GET SINGLE PRODUCT ------------------
@product_bp.route("/products/<int:id>", methods=["GET"])
def get_product(id):
    try:
        product = Product.query.get_or_404(id)
        return jsonify(product.to_dict()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ------------------ UPDATE PRODUCT ------------------
@product_bp.route("/products/<int:id>", methods=["PUT"])
def update_product(id):
    try:
        product = Product.query.get_or_404(id)
        data = request.get_json()

        errors = validate_product_data(data)
        if errors:
            return jsonify({"errors": errors}), 400

        if data.get('name') is not None:
            product.name = data['name'].strip()
        if data.get('quantity') is not None:
            product.quantity = int(data['quantity'])
        if data.get('model') is not None:
            product.model = data['model'].strip()
        if data.get('type') is not None:
            product.type = data['type'].strip()
        if data.get('watts') is not None:
            product.watts = float(data['watts']) if data['watts'] else None
        if data.get('buyPrice') is not None:
            product.buy_price = float(data['buyPrice'])
        if data.get('sellPrice') is not None:
            product.sell_price = float(data['sellPrice'])
        if data.get('category') is not None:
            product.category = data['category'].strip()

        db.session.commit()

        return jsonify(product.to_dict()), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400


# ------------------ DELETE PRODUCT ------------------
@product_bp.route("/products/<int:id>", methods=["DELETE"])
def delete_product(id):
    try:
        product = Product.query.get_or_404(id)
        db.session.delete(product)
        db.session.commit()
        return jsonify({"message": "Product deleted successfully"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400


# ------------------ BULK CREATE PRODUCTS ------------------
@product_bp.route("/products/bulk", methods=["POST"])
def bulk_create_products():
    try:
        data = request.get_json()
        products = data.get('products', [])

        if not products:
            return jsonify({"error": "No products provided"}), 400

        created_products = []
        errors = []

        for idx, product_data in enumerate(products):
            try:
                validation_errors = validate_product_data(product_data)
                if validation_errors:
                    errors.append({'index': idx, 'errors': validation_errors, 'data': product_data})
                    continue

                product = Product(
                    name=product_data.get("name", "").strip(),
                    quantity=int(product_data.get("quantity", 0)),
                    volume=product_data.get("volume", "").strip(),
                    hsn_code=product_data.get("hsnCode", "").strip(),
                    sell_price=float(product_data.get("sellPrice", 0)),
                    category=product_data.get("category", "").strip(),
                )

                db.session.add(product)
                created_products.append(product)

            except Exception as e:
                errors.append({'index': idx, 'error': str(e), 'data': product_data})

        if created_products:
            db.session.commit()

        return jsonify({
            'created': [p.to_dict() for p in created_products],
            'errors': errors,
            'total_created': len(created_products),
            'total_errors': len(errors)
        }), 201 if created_products else 400

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400


# ------------------ PRODUCT STATISTICS ------------------
@product_bp.route("/products/statistics", methods=["GET"])
def get_product_statistics():
    try:
        from sqlalchemy import func

        stats = db.session.query(
            func.count(Product.id).label('total_products'),
            func.sum(Product.quantity).label('total_quantity'),
            func.avg(Product.sell_price).label('avg_sell_price'),
        ).first()

        return jsonify({
            'total_products': stats.total_products or 0,
            'total_quantity': stats.total_quantity or 0,
            'average_rate': round(stats.avg_sell_price or 0, 2),
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 400