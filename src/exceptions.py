class ModelNotFound(Exception):
    message: str = "Model not found!"


class ProductNotFound(ModelNotFound):
    message: str = "Product not found :)"

