"""Pydantic models for the Strapi CMS planning output."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


FieldType = Literal[
    "string",
    "text",
    "richtext",
    "boolean",
    "integer",
    "decimal",
    "email",
    "json",
    "media",
    "component",
    "dynamiczone",
]

ComponentHandling = Literal["global_single_type", "ignore_existing_layout"]
PageKind = Literal["singleType"]

SNAKE_CASE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
KEBAB_CASE_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")
UID_PATTERN = re.compile(r"^[a-z][a-z0-9-]*\.[a-z][a-z0-9-]*$")


class FieldPlan(BaseModel):
    name: str
    type: FieldType
    required: bool = False
    component: str | None = None
    repeatable: bool | None = None
    multiple: bool | None = None
    allowedTypes: list[str] | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not SNAKE_CASE_PATTERN.match(value):
            raise ValueError("field name must be snake_case")
        return value

    @model_validator(mode="after")
    def validate_component_fields(self) -> "FieldPlan":
        if self.type == "component" and not self.component:
            raise ValueError("component fields must include a component uid")
        if self.type == "media" and self.multiple is None:
            self.multiple = False
        return self


class ComponentPlan(BaseModel):
    uid: str
    category: str
    displayName: str
    fileName: str
    fields: list[FieldPlan]

    @field_validator("uid")
    @classmethod
    def validate_uid(cls, value: str) -> str:
        if not UID_PATTERN.match(value):
            raise ValueError("component uid must look like category.component-name")
        return value

    @field_validator("category", "fileName")
    @classmethod
    def validate_kebab_case(cls, value: str) -> str:
        if not KEBAB_CASE_PATTERN.match(value):
            raise ValueError("category and fileName must be kebab-case")
        return value


class SingleTypeAttribute(BaseModel):
    name: str
    type: FieldType
    component: str | None = None
    repeatable: bool | None = None
    sourceSectionIndex: int | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not SNAKE_CASE_PATTERN.match(value):
            raise ValueError("single type attribute name must be snake_case")
        return value

    @model_validator(mode="after")
    def validate_component_attribute(self) -> "SingleTypeAttribute":
        if self.type == "component" and not self.component:
            raise ValueError("component attributes must include a component uid")
        return self


class PageModel(BaseModel):
    kind: PageKind
    apiName: str
    displayName: str
    singularName: str
    pluralName: str
    description: str = ""

    @field_validator("apiName", "singularName", "pluralName")
    @classmethod
    def validate_api_names(cls, value: str) -> str:
        if not KEBAB_CASE_PATTERN.match(value):
            raise ValueError("API names must be kebab-case")
        return value


class SeoPlan(BaseModel):
    enabled: bool = True
    component: str = "shared.seo"


class GlobalBlockPlan(BaseModel):
    handling: ComponentHandling
    apiName: str | None = None
    componentPlan: str | None = None

    @field_validator("apiName")
    @classmethod
    def validate_api_name(cls, value: str | None) -> str | None:
        if value is not None and not KEBAB_CASE_PATTERN.match(value):
            raise ValueError("global block apiName must be kebab-case")
        return value


class GlobalBlocksPlan(BaseModel):
    header: GlobalBlockPlan | None = None
    footer: GlobalBlockPlan | None = None


class CmsPlan(BaseModel):
    pageModel: PageModel
    seo: SeoPlan = Field(default_factory=SeoPlan)
    globalBlocks: GlobalBlocksPlan = Field(default_factory=GlobalBlocksPlan)
    components: list[ComponentPlan]
    singleTypeAttributes: list[SingleTypeAttribute]
    seedData: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_plan_integrity(self) -> "CmsPlan":
        component_uids = [component.uid for component in self.components]
        if len(component_uids) != len(set(component_uids)):
            raise ValueError("component UIDs must be unique")

        available_components = set(component_uids) | {"shared.link", "shared.seo"}
        for component in self.components:
            for field in component.fields:
                if field.component and field.component not in available_components:
                    raise ValueError(f"unknown component reference: {field.component}")

        attribute_names = [attribute.name for attribute in self.singleTypeAttributes]
        if len(attribute_names) != len(set(attribute_names)):
            raise ValueError("single type attributes must be unique")

        seed_keys = set(self.seedData.keys())
        attribute_keys = set(attribute_names)
        unknown_seed_keys = seed_keys - attribute_keys
        if unknown_seed_keys:
            raise ValueError(f"seedData has keys not present in attributes: {unknown_seed_keys}")

        return self
