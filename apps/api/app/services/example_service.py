from app.models.example import ExampleModel


class ExampleService:
    @staticmethod
    def create_example(name: str) -> ExampleModel:
        return ExampleModel(name=name)
