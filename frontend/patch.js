import fs from 'fs';
const pkg = JSON.parse(fs.readFileSync('package.json'));
pkg.pnpm = { overrides: { sass: "1.79.5" } };
fs.writeFileSync('package.json', JSON.stringify(pkg, null, 2));
