import type { Schema, Struct } from '@strapi/strapi';

export interface LandingPageContact extends Struct.ComponentSchema {
  collectionName: 'components_landing_page_contact';
  info: {
    displayName: 'Contact';
  };
  attributes: {
    description: Schema.Attribute.Text;
    form: Schema.Attribute.Component<'landing-page.form-config', false>;
    title: Schema.Attribute.String & Schema.Attribute.Required;
  };
}

export interface LandingPageContentItem extends Struct.ComponentSchema {
  collectionName: 'components_landing_page_content_item';
  info: {
    displayName: 'Content Item';
  };
  attributes: {
    author_name: Schema.Attribute.String;
    author_role: Schema.Attribute.String;
    cta: Schema.Attribute.Component<'shared.link', false>;
    description: Schema.Attribute.Text;
    image: Schema.Attribute.Media<'images'>;
    label: Schema.Attribute.String;
    quote: Schema.Attribute.Text;
    text: Schema.Attribute.Text;
    title: Schema.Attribute.String;
    value: Schema.Attribute.String;
  };
}

export interface LandingPageContentSection extends Struct.ComponentSchema {
  collectionName: 'components_landing_page_content_section';
  info: {
    displayName: 'Content Section';
  };
  attributes: {
    actions: Schema.Attribute.Component<'shared.link', true>;
    body: Schema.Attribute.Text;
    description: Schema.Attribute.Text;
    eyebrow: Schema.Attribute.String;
    form: Schema.Attribute.JSON;
    items: Schema.Attribute.Component<'landing-page.content-item', true>;
    metadata: Schema.Attribute.JSON;
    table: Schema.Attribute.JSON;
    title: Schema.Attribute.String;
  };
}

export interface LandingPageFaq extends Struct.ComponentSchema {
  collectionName: 'components_landing_page_faq';
  info: {
    displayName: 'FAQ';
  };
  attributes: {
    items: Schema.Attribute.Component<'landing-page.faq-item', true>;
    title: Schema.Attribute.String & Schema.Attribute.Required;
  };
}

export interface LandingPageFaqItem extends Struct.ComponentSchema {
  collectionName: 'components_landing_page_faq_item';
  info: {
    displayName: 'FAQ Item';
  };
  attributes: {
    answer: Schema.Attribute.Text & Schema.Attribute.Required;
    question: Schema.Attribute.String & Schema.Attribute.Required;
  };
}

export interface LandingPageFeatureCard extends Struct.ComponentSchema {
  collectionName: 'components_landing_page_feature_card';
  info: {
    displayName: 'Feature Card';
  };
  attributes: {
    description: Schema.Attribute.Text;
    title: Schema.Attribute.String & Schema.Attribute.Required;
  };
}

export interface LandingPageFeatures extends Struct.ComponentSchema {
  collectionName: 'components_landing_page_features';
  info: {
    displayName: 'Features';
  };
  attributes: {
    description: Schema.Attribute.Text;
    items: Schema.Attribute.Component<'landing-page.feature-card', true>;
    title: Schema.Attribute.String & Schema.Attribute.Required;
  };
}

export interface LandingPageFormConfig extends Struct.ComponentSchema {
  collectionName: 'components_landing_page_form_config';
  info: {
    displayName: 'Form Config';
  };
  attributes: {
    action: Schema.Attribute.String;
    fields: Schema.Attribute.Component<'landing-page.form-field', true>;
    method: Schema.Attribute.String;
    submit_label: Schema.Attribute.String;
  };
}

export interface LandingPageFormField extends Struct.ComponentSchema {
  collectionName: 'components_landing_page_form_field';
  info: {
    displayName: 'Form Field';
  };
  attributes: {
    input_type: Schema.Attribute.String;
    label: Schema.Attribute.String;
    name: Schema.Attribute.String & Schema.Attribute.Required;
    required: Schema.Attribute.Boolean;
  };
}

export interface LandingPageHero extends Struct.ComponentSchema {
  collectionName: 'components_landing_page_hero';
  info: {
    displayName: 'Hero';
  };
  attributes: {
    description: Schema.Attribute.Text;
    eyebrow: Schema.Attribute.String;
    image: Schema.Attribute.Media<'images'>;
    primary_cta: Schema.Attribute.Component<'shared.link', false>;
    secondary_cta: Schema.Attribute.Component<'shared.link', false>;
    title: Schema.Attribute.String & Schema.Attribute.Required;
  };
}

export interface LandingPagePricing extends Struct.ComponentSchema {
  collectionName: 'components_landing_page_pricing';
  info: {
    displayName: 'Pricing';
  };
  attributes: {
    items: Schema.Attribute.Component<'landing-page.pricing-card', true>;
    title: Schema.Attribute.String & Schema.Attribute.Required;
  };
}

export interface LandingPagePricingCard extends Struct.ComponentSchema {
  collectionName: 'components_landing_page_pricing_card';
  info: {
    displayName: 'Pricing Card';
  };
  attributes: {
    description: Schema.Attribute.Text;
    features: Schema.Attribute.Component<'landing-page.pricing-feature', true>;
    is_highlighted: Schema.Attribute.Boolean;
    price: Schema.Attribute.String;
    title: Schema.Attribute.String & Schema.Attribute.Required;
  };
}

export interface LandingPagePricingFeature extends Struct.ComponentSchema {
  collectionName: 'components_landing_page_pricing_feature';
  info: {
    displayName: 'Pricing Feature';
  };
  attributes: {
    text: Schema.Attribute.String & Schema.Attribute.Required;
  };
}

export interface LandingPageTestimonialCard extends Struct.ComponentSchema {
  collectionName: 'components_landing_page_testimonial_card';
  info: {
    displayName: 'Testimonial Card';
  };
  attributes: {
    author_name: Schema.Attribute.String;
    author_role: Schema.Attribute.String;
    quote: Schema.Attribute.Text & Schema.Attribute.Required;
  };
}

export interface LandingPageTestimonials extends Struct.ComponentSchema {
  collectionName: 'components_landing_page_testimonials';
  info: {
    displayName: 'Testimonials';
  };
  attributes: {
    items: Schema.Attribute.Component<'landing-page.testimonial-card', true>;
    title: Schema.Attribute.String & Schema.Attribute.Required;
  };
}

export interface SharedLink extends Struct.ComponentSchema {
  collectionName: 'components_shared_link';
  info: {
    displayName: 'Link';
  };
  attributes: {
    text: Schema.Attribute.String & Schema.Attribute.Required;
    url: Schema.Attribute.String & Schema.Attribute.Required;
  };
}

export interface SharedSeo extends Struct.ComponentSchema {
  collectionName: 'components_shared_seo';
  info: {
    displayName: 'SEO';
  };
  attributes: {
    meta_description: Schema.Attribute.Text;
    meta_title: Schema.Attribute.String;
  };
}

declare module '@strapi/strapi' {
  export module Public {
    export interface ComponentSchemas {
      'landing-page.contact': LandingPageContact;
      'landing-page.content-item': LandingPageContentItem;
      'landing-page.content-section': LandingPageContentSection;
      'landing-page.faq': LandingPageFaq;
      'landing-page.faq-item': LandingPageFaqItem;
      'landing-page.feature-card': LandingPageFeatureCard;
      'landing-page.features': LandingPageFeatures;
      'landing-page.form-config': LandingPageFormConfig;
      'landing-page.form-field': LandingPageFormField;
      'landing-page.hero': LandingPageHero;
      'landing-page.pricing': LandingPagePricing;
      'landing-page.pricing-card': LandingPagePricingCard;
      'landing-page.pricing-feature': LandingPagePricingFeature;
      'landing-page.testimonial-card': LandingPageTestimonialCard;
      'landing-page.testimonials': LandingPageTestimonials;
      'shared.link': SharedLink;
      'shared.seo': SharedSeo;
    }
  }
}
