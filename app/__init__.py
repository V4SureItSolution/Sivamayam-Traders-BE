from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from config import Config

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()


def create_app():
    app = Flask(__name__)
    CORS(app)
    print("Creating Flask App...")
    app.config.from_object(Config)

    # Initialize database
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Initialize JWT
    jwt.init_app(app)

    # Enable CORS - allow specific origins for credentials mode
    CORS(
        app,
        supports_credentials=True,
        resources={r"/*": {"origins": [
            "http://localhost:3000",
            "http://localhost:3001",  # ← ADDED: your React is running on 3001
            "http://localhost:5000"
        ]}},
    )

    # Import models so Flask-Migrate detects them
    from app import models

    # Register Blueprints
    from app.routes.login_routes import login_bp
    from app.routes.product_routes import product_bp
    from app.routes.billing_routes import billing_bp
    from app.routes.supplier_routes import supplier_bp
    from app.routes.quotation_routes import quotation_bp
    from app.routes.invoice_routes import invoice_bp
    from app.routes.service_routes import service_bp
    from app.routes.usertype_routes import user_type_bp
    from app.routes.employee_routes import employee_bp
    from app.routes.attendance_routes import attendance_bp
    from app.routes.current_company_routes import company_bp
    from app.routes.enquiry_routes import enquiry_bp
    from app.routes.discount_routes import discount_bp
    from app.routes.permissions_routes import permissions_bp
    from app.routes.payment_routes import payment_tracking_bp

    app.register_blueprint(login_bp, url_prefix="/api")
    app.register_blueprint(product_bp, url_prefix="/api")
    app.register_blueprint(billing_bp, url_prefix="/api")
    app.register_blueprint(supplier_bp)
    app.register_blueprint(quotation_bp, url_prefix='/api')
    app.register_blueprint(invoice_bp, url_prefix='/api')
    app.register_blueprint(service_bp)
    app.register_blueprint(user_type_bp)
    app.register_blueprint(employee_bp, url_prefix="/api")
    app.register_blueprint(attendance_bp)
    app.register_blueprint(company_bp)
    app.register_blueprint(enquiry_bp, url_prefix="/api")
    app.register_blueprint(discount_bp)
    app.register_blueprint(permissions_bp)
    app.register_blueprint(payment_tracking_bp)

    @app.route('/', methods=['GET'])
    def index():
        return {
            "status": "running",
            "message": "Sivamayam Traders backend is working",
            "health_url": "/api/health"
        }, 200

    # Health Check Route
    @app.route('/api/health', methods=['GET'])
    def health_check():
        return {
            "status": "healthy",
            "message": "API is working"
        }, 200

    return app