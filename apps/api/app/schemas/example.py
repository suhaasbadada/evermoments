from pydantic import BaseModel


class ExampleBase(BaseModel):
    name: str


class ExampleCreate(ExampleBase):
    pass


class ExampleRead(ExampleBase):
    id: int

    model_config = {"from_attributes": True}
