// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

export default defineConfig({
	// region:astro-base-config
	site: 'https://jkstandards.jk.digital',
	// endregion:astro-base-config
	integrations: [
		starlight({
			title: 'jk-standards',
			description:
				'Reusable engineering-discipline toolkit: documentation anti-drift checks, pre-commit hooks, reusable CI workflows, and agent skills.',
			social: [
				{
					icon: 'github',
					label: 'GitHub',
					href: 'https://github.com/JimAKennedy/jk-standards',
				},
			],
			customCss: ['./src/styles/custom.css'],
			sidebar: [
				{
					label: 'Guide',
					items: [
						{ label: 'Introduction', slug: 'guide/introduction' },
						{ label: 'Quickstart', slug: 'guide/quickstart' },
					],
				},
				{
					label: 'Reference',
					items: [
						{ label: 'Checks', slug: 'reference/checks' },
						{ label: 'Configuration', slug: 'reference/configuration' },
						{ label: 'Skills', slug: 'reference/skills' },
					],
				},
				{
					label: 'How-to',
					items: [
						{ label: 'Adopt in a repo', slug: 'how-to/adopt-in-a-repo' },
						{ label: 'Add a check', slug: 'how-to/add-a-check' },
					],
				},
			],
		}),
	],
});
