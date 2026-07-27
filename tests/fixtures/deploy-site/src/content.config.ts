import { defineCollection } from 'astro:content';
import { docsLoader } from '@astrojs/starlight/loaders';
import { docsSchema } from '@astrojs/starlight/schema';

// Mirrors the real site's docs collection so the fixture is a faithful minimal
// Starlight setup (docsLoader reads from src/content/docs/).
export const collections = {
	docs: defineCollection({ loader: docsLoader(), schema: docsSchema() }),
};
