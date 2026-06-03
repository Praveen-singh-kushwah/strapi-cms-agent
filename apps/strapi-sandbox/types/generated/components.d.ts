import type { Schema, Struct } from '@strapi/strapi';

export interface LandingPageCalculator extends Struct.ComponentSchema {
  collectionName: 'components_landing_page_calculator';
  info: {
    displayName: 'Calculator';
  };
  attributes: {
    actions: Schema.Attribute.Component<'shared.link', true>;
    body: Schema.Attribute.Text;
    description: Schema.Attribute.Text;
    eyebrow: Schema.Attribute.String;
    form: Schema.Attribute.JSON;
    items: Schema.Attribute.Component<'landing-page.calculator-result', true>;
    metadata: Schema.Attribute.JSON;
    table: Schema.Attribute.JSON;
    title: Schema.Attribute.String & Schema.Attribute.Required;
  };
}

export interface LandingPageCalculatorResult extends Struct.ComponentSchema {
  collectionName: 'components_landing_page_calculator_result';
  info: {
    displayName: 'Calculator Result';
  };
  attributes: {
    author_name: Schema.Attribute.String;
    author_role: Schema.Attribute.String;
    cta: Schema.Attribute.Component<'shared.link', false>;
    description: Schema.Attribute.Text;
    features: Schema.Attribute.JSON;
    image: Schema.Attribute.Media<'images'>;
    label: Schema.Attribute.String;
    period: Schema.Attribute.String;
    price: Schema.Attribute.String;
    quote: Schema.Attribute.Text;
    saving: Schema.Attribute.String;
    text: Schema.Attribute.Text;
    title: Schema.Attribute.String;
    value: Schema.Attribute.String;
  };
}

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

export interface LandingPageCta extends Struct.ComponentSchema {
  collectionName: 'components_landing_page_cta';
  info: {
    displayName: 'CTA';
  };
  attributes: {
    actions: Schema.Attribute.Component<'shared.link', true>;
    body: Schema.Attribute.Text;
    description: Schema.Attribute.Text;
    eyebrow: Schema.Attribute.String;
    form: Schema.Attribute.JSON;
    items: Schema.Attribute.Component<'landing-page.cta-item', true>;
    metadata: Schema.Attribute.JSON;
    table: Schema.Attribute.JSON;
    title: Schema.Attribute.String & Schema.Attribute.Required;
  };
}

export interface LandingPageCtaItem extends Struct.ComponentSchema {
  collectionName: 'components_landing_page_cta_item';
  info: {
    displayName: 'CTA Item';
  };
  attributes: {
    author_name: Schema.Attribute.String;
    author_role: Schema.Attribute.String;
    cta: Schema.Attribute.Component<'shared.link', false>;
    description: Schema.Attribute.Text;
    features: Schema.Attribute.JSON;
    image: Schema.Attribute.Media<'images'>;
    label: Schema.Attribute.String;
    period: Schema.Attribute.String;
    price: Schema.Attribute.String;
    quote: Schema.Attribute.Text;
    saving: Schema.Attribute.String;
    text: Schema.Attribute.Text;
    title: Schema.Attribute.String;
    value: Schema.Attribute.String;
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

export interface LandingPageGuarantee extends Struct.ComponentSchema {
  collectionName: 'components_landing_page_guarantee';
  info: {
    displayName: 'Guarantee';
  };
  attributes: {
    actions: Schema.Attribute.Component<'shared.link', true>;
    body: Schema.Attribute.Text;
    description: Schema.Attribute.Text;
    eyebrow: Schema.Attribute.String;
    form: Schema.Attribute.JSON;
    items: Schema.Attribute.Component<'landing-page.guarantee-item', true>;
    metadata: Schema.Attribute.JSON;
    table: Schema.Attribute.JSON;
    title: Schema.Attribute.String & Schema.Attribute.Required;
  };
}

export interface LandingPageGuaranteeItem extends Struct.ComponentSchema {
  collectionName: 'components_landing_page_guarantee_item';
  info: {
    displayName: 'Guarantee Item';
  };
  attributes: {
    author_name: Schema.Attribute.String;
    author_role: Schema.Attribute.String;
    cta: Schema.Attribute.Component<'shared.link', false>;
    description: Schema.Attribute.Text;
    features: Schema.Attribute.JSON;
    image: Schema.Attribute.Media<'images'>;
    label: Schema.Attribute.String;
    period: Schema.Attribute.String;
    price: Schema.Attribute.String;
    quote: Schema.Attribute.Text;
    saving: Schema.Attribute.String;
    text: Schema.Attribute.Text;
    title: Schema.Attribute.String;
    value: Schema.Attribute.String;
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

export interface LandingPageProcess extends Struct.ComponentSchema {
  collectionName: 'components_landing_page_process';
  info: {
    displayName: 'Process';
  };
  attributes: {
    actions: Schema.Attribute.Component<'shared.link', true>;
    body: Schema.Attribute.Text;
    description: Schema.Attribute.Text;
    eyebrow: Schema.Attribute.String;
    form: Schema.Attribute.JSON;
    items: Schema.Attribute.Component<'landing-page.process-step', true>;
    metadata: Schema.Attribute.JSON;
    table: Schema.Attribute.JSON;
    title: Schema.Attribute.String & Schema.Attribute.Required;
  };
}

export interface LandingPageProcessStep extends Struct.ComponentSchema {
  collectionName: 'components_landing_page_process_step';
  info: {
    displayName: 'Process Step';
  };
  attributes: {
    author_name: Schema.Attribute.String;
    author_role: Schema.Attribute.String;
    cta: Schema.Attribute.Component<'shared.link', false>;
    description: Schema.Attribute.Text;
    features: Schema.Attribute.JSON;
    image: Schema.Attribute.Media<'images'>;
    label: Schema.Attribute.String;
    period: Schema.Attribute.String;
    price: Schema.Attribute.String;
    quote: Schema.Attribute.Text;
    saving: Schema.Attribute.String;
    text: Schema.Attribute.Text;
    title: Schema.Attribute.String;
    value: Schema.Attribute.String;
  };
}

export interface LandingPageResultItem extends Struct.ComponentSchema {
  collectionName: 'components_landing_page_result_item';
  info: {
    displayName: 'Result Item';
  };
  attributes: {
    author_name: Schema.Attribute.String;
    author_role: Schema.Attribute.String;
    cta: Schema.Attribute.Component<'shared.link', false>;
    description: Schema.Attribute.Text;
    features: Schema.Attribute.JSON;
    image: Schema.Attribute.Media<'images'>;
    label: Schema.Attribute.String;
    period: Schema.Attribute.String;
    price: Schema.Attribute.String;
    quote: Schema.Attribute.Text;
    saving: Schema.Attribute.String;
    text: Schema.Attribute.Text;
    title: Schema.Attribute.String;
    value: Schema.Attribute.String;
  };
}

export interface LandingPageResultsTable extends Struct.ComponentSchema {
  collectionName: 'components_landing_page_results_table';
  info: {
    displayName: 'Results Table';
  };
  attributes: {
    actions: Schema.Attribute.Component<'shared.link', true>;
    body: Schema.Attribute.Text;
    description: Schema.Attribute.Text;
    eyebrow: Schema.Attribute.String;
    form: Schema.Attribute.JSON;
    items: Schema.Attribute.Component<'landing-page.result-item', true>;
    metadata: Schema.Attribute.JSON;
    table: Schema.Attribute.JSON;
    title: Schema.Attribute.String & Schema.Attribute.Required;
  };
}

export interface LandingPageStatItem extends Struct.ComponentSchema {
  collectionName: 'components_landing_page_stat_item';
  info: {
    displayName: 'Stat Item';
  };
  attributes: {
    author_name: Schema.Attribute.String;
    author_role: Schema.Attribute.String;
    cta: Schema.Attribute.Component<'shared.link', false>;
    description: Schema.Attribute.Text;
    features: Schema.Attribute.JSON;
    image: Schema.Attribute.Media<'images'>;
    label: Schema.Attribute.String;
    period: Schema.Attribute.String;
    price: Schema.Attribute.String;
    quote: Schema.Attribute.Text;
    saving: Schema.Attribute.String;
    text: Schema.Attribute.Text;
    title: Schema.Attribute.String;
    value: Schema.Attribute.String;
  };
}

export interface LandingPageStatsBand extends Struct.ComponentSchema {
  collectionName: 'components_landing_page_stats_band';
  info: {
    displayName: 'Stats Band';
  };
  attributes: {
    actions: Schema.Attribute.Component<'shared.link', true>;
    body: Schema.Attribute.Text;
    description: Schema.Attribute.Text;
    eyebrow: Schema.Attribute.String;
    form: Schema.Attribute.JSON;
    items: Schema.Attribute.Component<'landing-page.stat-item', true>;
    metadata: Schema.Attribute.JSON;
    table: Schema.Attribute.JSON;
    title: Schema.Attribute.String & Schema.Attribute.Required;
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

export interface LandingPageTimeline extends Struct.ComponentSchema {
  collectionName: 'components_landing_page_timeline';
  info: {
    displayName: 'Timeline';
  };
  attributes: {
    actions: Schema.Attribute.Component<'shared.link', true>;
    body: Schema.Attribute.Text;
    description: Schema.Attribute.Text;
    eyebrow: Schema.Attribute.String;
    form: Schema.Attribute.JSON;
    items: Schema.Attribute.Component<'landing-page.timeline-item', true>;
    metadata: Schema.Attribute.JSON;
    table: Schema.Attribute.JSON;
    title: Schema.Attribute.String & Schema.Attribute.Required;
  };
}

export interface LandingPageTimelineItem extends Struct.ComponentSchema {
  collectionName: 'components_landing_page_timeline_item';
  info: {
    displayName: 'Timeline Item';
  };
  attributes: {
    author_name: Schema.Attribute.String;
    author_role: Schema.Attribute.String;
    cta: Schema.Attribute.Component<'shared.link', false>;
    description: Schema.Attribute.Text;
    features: Schema.Attribute.JSON;
    image: Schema.Attribute.Media<'images'>;
    label: Schema.Attribute.String;
    period: Schema.Attribute.String;
    price: Schema.Attribute.String;
    quote: Schema.Attribute.Text;
    saving: Schema.Attribute.String;
    text: Schema.Attribute.Text;
    title: Schema.Attribute.String;
    value: Schema.Attribute.String;
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
      'landing-page.calculator': LandingPageCalculator;
      'landing-page.calculator-result': LandingPageCalculatorResult;
      'landing-page.contact': LandingPageContact;
      'landing-page.content-item': LandingPageContentItem;
      'landing-page.content-section': LandingPageContentSection;
      'landing-page.cta': LandingPageCta;
      'landing-page.cta-item': LandingPageCtaItem;
      'landing-page.faq': LandingPageFaq;
      'landing-page.faq-item': LandingPageFaqItem;
      'landing-page.feature-card': LandingPageFeatureCard;
      'landing-page.features': LandingPageFeatures;
      'landing-page.form-config': LandingPageFormConfig;
      'landing-page.form-field': LandingPageFormField;
      'landing-page.guarantee': LandingPageGuarantee;
      'landing-page.guarantee-item': LandingPageGuaranteeItem;
      'landing-page.hero': LandingPageHero;
      'landing-page.pricing': LandingPagePricing;
      'landing-page.pricing-card': LandingPagePricingCard;
      'landing-page.pricing-feature': LandingPagePricingFeature;
      'landing-page.process': LandingPageProcess;
      'landing-page.process-step': LandingPageProcessStep;
      'landing-page.result-item': LandingPageResultItem;
      'landing-page.results-table': LandingPageResultsTable;
      'landing-page.stat-item': LandingPageStatItem;
      'landing-page.stats-band': LandingPageStatsBand;
      'landing-page.testimonial-card': LandingPageTestimonialCard;
      'landing-page.testimonials': LandingPageTestimonials;
      'landing-page.timeline': LandingPageTimeline;
      'landing-page.timeline-item': LandingPageTimelineItem;
      'shared.link': SharedLink;
      'shared.seo': SharedSeo;
    }
  }
}
