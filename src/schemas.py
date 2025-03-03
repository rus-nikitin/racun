from pydantic import BaseModel


class RacunBase(BaseModel):
    class Config:
        validate_assignment = True
        str_strip_whitespace = True
