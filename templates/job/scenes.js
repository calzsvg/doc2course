// One factory per scene id in script.json. See references/scene-authoring.md (and references/long-form.md for long videos).
// Long videos: one file per chapter, re-exported here, e.g. export { ch2, ch2_concept } from './scenes_joins.js';
import { titleCard } from '/engine/templates.js';

export const title = () => titleCard({ title: 'Document title', subtitle: 'One-line hook', tag: 'source · month' });   // starter only: replace in step 6
