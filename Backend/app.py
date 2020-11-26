import config

from flask      import Flask, jsonify
from flask_cors import CORS

from model.user_dao       import UserDao, SellerDao
from service.user_service import UserService, SellerService
from view.user_view       import UserView, SellerView
from utils.exceptions     import ApiError


class Services:
    pass


def create_app(test_config=None):
    app = Flask(__name__)
    app.debug = True

    CORS(app, resources={r'*': {'origins': '*'}})

    if test_config is None:
        app.config.from_pyfile("config.py")
    else:
        app.config.update(test_config)

    # Persistence Layer
    user_dao = UserDao()
    seller_dao = SellerDao()

    # Business Layer
    services = Services
    services.user_service = UserService(user_dao, config)
    services.seller_service = SellerService(seller_dao, config)

    # Endpoint
    UserView.create_endpoints(app, services)
    SellerView.create_endpoints(app, services)

    @app.errorhandler(Exception)
    def handle_error(error):
        if type(error) is ApiError:
            return jsonify({'message': 'error {}'.format(error.message)}), error.status_code
        return jsonify({'message': 'error {}'.format(error)}), 500
    return app
