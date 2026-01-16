Diagrams in this folder are authored in Mermaid syntax (`.mmd`) and can be rendered using several tools.

Options to render locally:

1. VS Code + "Markdown Preview Mermaid Support" or "Mermaid Markdown Preview" extension — open the `.mmd` file and preview.

2. `mmdc` (Mermaid CLI) — install with npm:

```bash
npm install -g @mermaid-js/mermaid-cli
```

Render to PNG/SVG:

```bash
mmdc -i ER_diagram.mmd -o ER_diagram.png
mmdc -i class_diagram.mmd -o class_diagram.png
```

3. Use online editors like https://mermaid.live to paste and export.

If you want me to render PNGs and add them to the repo, I can try using `mmdc` in the CI or create rendered images locally if you approve adding generated images to source control.

Automation
----------

Rendering and CI
----------------

This repository keeps source Mermaid files (`.mmd`) in this folder and embeds Mermaid code blocks in `docs/ARCHITECTURE.md` so supported renderers (including GitHub) display diagrams inline.

If you prefer to render images locally, install the Mermaid CLI and run:

```bash
npm install -g @mermaid-js/mermaid-cli
mmdc -i ER_diagram.mmd -o ER_diagram.png
mmdc -i class_diagram.mmd -o class_diagram.png
```

For quick previews, use https://mermaid.live or a VS Code Mermaid preview extension.