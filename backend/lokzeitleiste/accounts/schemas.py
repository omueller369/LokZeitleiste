from datetime import date
from pydantic import BaseModel, Field, field_validator, model_validator
from .access import MODULES


class AddressIn(BaseModel):
    street: str = Field(min_length=1,max_length=200)
    house_number: str = Field(min_length=1,max_length=30)
    postal_code: str = Field(min_length=1,max_length=20)
    city: str = Field(min_length=1,max_length=120)

    @field_validator('street','house_number','postal_code','city')
    @classmethod
    def not_blank(cls,value):
        if not value.strip():
            raise ValueError('Pflichtfeld darf nicht leer sein')
        return value.strip()


class StaffIn(BaseModel):
    photo_base64: str | None = Field(default=None,max_length=6990510)
    first_name: str = Field(min_length=1,max_length=120)
    last_name: str = Field(min_length=1,max_length=120)
    nationality: str = Field(min_length=1,max_length=120)
    birth_date: date
    cost_center: str = Field(min_length=1,max_length=80)
    addresses: list[AddressIn] = Field(min_length=1,max_length=10)
    permissions: dict[str,int]

    @field_validator('first_name','last_name','nationality','cost_center')
    @classmethod
    def not_blank(cls,value):
        if not value.strip():
            raise ValueError('Pflichtfeld darf nicht leer sein')
        return value.strip()

    @model_validator(mode='after')
    def validate_fields(self):
        if self.birth_date > date.today():
            raise ValueError('Geburtsdatum darf nicht in der Zukunft liegen')
        if set(self.permissions) - MODULES.keys() or any(type(v) is not int or not 0 <= v <= 3 for v in self.permissions.values()):
            raise ValueError('Ungültige Modulberechtigung')
        self.permissions = {m:self.permissions.get(m,0) for m in MODULES}
        return self


class StaffCreate(StaffIn):
    username: str = Field(pattern=r'^[a-z0-9._-]{3,64}$')
    initial_password: str = Field(min_length=12,max_length=4096)


class PasswordChange(BaseModel):
    current_password: str = Field(max_length=4096)
    new_password: str = Field(min_length=12,max_length=4096)
    confirm_password: str = Field(min_length=12,max_length=4096)

    @model_validator(mode='after')
    def confirm(self):
        if self.new_password != self.confirm_password:
            raise ValueError('Passwörter stimmen nicht überein')
        return self


class PasswordReset(BaseModel):
    initial_password: str = Field(min_length=12,max_length=4096)
