import { defineCollection } from 'astro:content';
import { docsLoader } from '@astrojs/starlight/loaders';
import { docsSchema } from '@astrojs/starlight/schema';

// region:docs-collection
export const collections = {
	docs: defineCollection({ loader: docsLoader(), schema: docsSchema() }),
};
// endregion:docs-collection
