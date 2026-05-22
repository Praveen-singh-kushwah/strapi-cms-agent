"""Pydantic models for the Strapi CMS planning output."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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
KNOWN_SHARED_COMPONENT_UIDS = {"shared.link", "shared.seo", "shared.text-item"}


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FieldPlan(StrictBaseModel):
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


class ComponentPlan(StrictBaseModel):
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


class SingleTypeAttribute(StrictBaseModel):
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


class PageModel(StrictBaseModel):
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


class SeoPlan(StrictBaseModel):
    enabled: bool = True
    component: str = "shared.seo"


class GlobalBlockPlan(StrictBaseModel):
    handling: ComponentHandling
    apiName: str | None = None
    componentPlan: str | None = None

    @field_validator("apiName")
    @classmethod
    def validate_api_name(cls, value: str | None) -> str | None:
        if value is not None and not KEBAB_CASE_PATTERN.match(value):
            raise ValueError("global block apiName must be kebab-case")
        return value


class GlobalBlocksPlan(StrictBaseModel):
    header: GlobalBlockPlan | None = None
    footer: GlobalBlockPlan | None = None


class LinkSeed(StrictBaseModel):
    text: str = ""
    url: str = ""


class ImageSeed(StrictBaseModel):
    src: str = ""
    alt: str = ""


class SeoSeed(StrictBaseModel):
    meta_title: str = ""
    meta_description: str = ""


class HeroSeed(StrictBaseModel):
    eyebrow: str = ""
    title: str = ""
    description: str = ""
    primary_cta: LinkSeed | None = None
    secondary_cta: LinkSeed | None = None
    image: ImageSeed | None = None


class FeatureCardSeed(StrictBaseModel):
    title: str = ""
    description: str = ""


class ItemsSectionSeed(StrictBaseModel):
    title: str = ""
    description: str = ""
    items: list[FeatureCardSeed] = Field(default_factory=list)


class TestimonialCardSeed(StrictBaseModel):
    quote: str = ""
    author_name: str = ""
    author_role: str = ""


class TestimonialsSeed(StrictBaseModel):
    title: str = ""
    description: str = ""
    items: list[TestimonialCardSeed] = Field(default_factory=list)


class PricingFeatureSeed(StrictBaseModel):
    text: str = ""


class PricingCardSeed(StrictBaseModel):
    title: str = ""
    price: str = ""
    description: str = ""
    features: list[PricingFeatureSeed] = Field(default_factory=list)
    is_highlighted: bool = False


class PricingSeed(StrictBaseModel):
    title: str = ""
    description: str = ""
    items: list[PricingCardSeed] = Field(default_factory=list)


class FaqItemSeed(StrictBaseModel):
    question: str = ""
    answer: str = ""


class FaqSeed(StrictBaseModel):
    title: str = ""
    description: str = ""
    items: list[FaqItemSeed] = Field(default_factory=list)


class FormFieldSeed(StrictBaseModel):
    label: str = ""
    name: str = ""
    input_type: str = ""
    required: bool = False


class FormConfigSeed(StrictBaseModel):
    action: str = ""
    method: str = ""
    submit_label: str = ""
    fields: list[FormFieldSeed] = Field(default_factory=list)


class ContactSeed(StrictBaseModel):
    title: str = ""
    description: str = ""
    form: FormConfigSeed = Field(default_factory=FormConfigSeed)


class SeedDataPlan(StrictBaseModel):
    seo: SeoSeed = Field(default_factory=SeoSeed)
    hero: HeroSeed | None = None
    features: ItemsSectionSeed | None = None
    testimonials: TestimonialsSeed | None = None
    pricing: PricingSeed | None = None
    faq: FaqSeed | None = None
    contact: ContactSeed | None = None


class CmsPlan(StrictBaseModel):
    pageModel: PageModel
    seo: SeoPlan = Field(default_factory=SeoPlan)
    globalBlocks: GlobalBlocksPlan = Field(default_factory=GlobalBlocksPlan)
    components: list[ComponentPlan]
    singleTypeAttributes: list[SingleTypeAttribute]
    seedData: SeedDataPlan
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_plan_integrity(self) -> "CmsPlan":
        component_uids = [component.uid for component in self.components]
        if len(component_uids) != len(set(component_uids)):
            raise ValueError("component UIDs must be unique")

        available_components = set(component_uids) | KNOWN_SHARED_COMPONENT_UIDS
        for component in self.components:
            for field in component.fields:
                if field.component and field.component not in available_components:
                    raise ValueError(f"unknown component reference: {field.component}")

        attribute_names = [attribute.name for attribute in self.singleTypeAttributes]
        if len(attribute_names) != len(set(attribute_names)):
            raise ValueError("single type attributes must be unique")

        seed_dict = self.seedData.model_dump(exclude_none=True)
        seed_keys = set(seed_dict.keys())
        attribute_keys = set(attribute_names)
        unknown_seed_keys = seed_keys - attribute_keys
        if unknown_seed_keys:
            raise ValueError(f"seedData has keys not present in attributes: {unknown_seed_keys}")

        return self
