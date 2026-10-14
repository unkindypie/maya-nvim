#!/usr/bin/env python3
"""Attachment and diagnostic smoke checks for the installed language inventory."""
from pathlib import Path
import tempfile
import subprocess
from integration import start, wait, stop

CASES = [
    ('typescript', 'sample.ts', 'const value: number = "wrong";\n', ['ts_ls']),
    ('json', 'sample.json', '{"value": }\n', ['jsonls']),
    ('yaml', 'sample.yaml', 'name: Maya\n', ['yamlls']),
    ('lua', 'sample.lua', 'local value = 1\nreturn value\n', ['lua_ls']),
    ('sh', 'sample.sh', '#!/usr/bin/env bash\necho "$HOME"\n', ['bashls']),
    ('dockerfile', 'Dockerfile', 'FROM alpine:3.22\nRUN echo hello\n', ['dockerls']),
    ('html', 'index.html', '<!doctype html><html><body>Hello</body></html>\n', ['html']),
    ('css', 'style.css', 'body { color: red; }\n', ['cssls']),
    ('markdown', 'README.md', '# Maya\n\n[link](README.md)\n', ['marksman']),
    ('hyprlang', 'hyprland.conf', 'general {\n  gaps_in = 5\n}\n', ['hyprls']),
]


def main():
    with tempfile.TemporaryDirectory(prefix='maya-languages-') as temp:
        root = Path(temp)
        (root / '.git').mkdir()
        (root / 'package.json').write_text('{"name":"maya-language-test","version":"1.0.0"}\n')
        (root / 'pyproject.toml').write_text('[project]\nname="maya-language-test"\nversion="1.0.0"\n')
        nvim = start()
        try:
            for ft, name, contents, servers in CASES:
                path = root / name
                path.write_text(contents)
                nvim.command('edit ' + nvim.funcs.fnameescape(str(path)))
                if nvim.current.buffer.options['filetype'] != ft:
                    nvim.command('setfiletype ' + ft)
                    nvim.current.buffer.options['filetype'] = ft
                for server in servers:
                    wait(nvim, '(function() for _,c in ipairs(vim.lsp.get_clients({bufnr=0})) do if c.name==' + repr(server) + ' then return true end end return false end)()', 60)
                wait(nvim, 'pcall(vim.treesitter.get_parser,0)', 30)
                if ft in ('typescript','json'):
                    wait(nvim, '#vim.diagnostic.get(0,{severity=vim.diagnostic.severity.ERROR})>0', 45)
                print('PASS ' + ft + ': ' + ', '.join(servers) + ', parser' + (' and expected error' if ft in ('typescript','json') else ''), flush=True)
        finally:
            stop(nvim)


def eslint_project():
    with tempfile.TemporaryDirectory(prefix='maya-eslint-') as temp:
        root = Path(temp)
        (root / 'package.json').write_text('{"name":"maya-eslint-test","version":"1.0.0","private":true}\n')
        subprocess.run(['npm','install','--prefix',temp,'--no-audit','--no-fund','--save-dev','eslint'],check=True,capture_output=True)
        (root / 'eslint.config.mjs').write_text('export default [{files:["**/*.js"],rules:{"no-unused-vars":"error"}}];\n')
        file = root / 'sample.js'; file.write_text('const unused = 1;\n')
        nvim = start()
        try:
            nvim.command('edit ' + str(file))
            wait(nvim, '(function() for _,c in ipairs(vim.lsp.get_clients({bufnr=0})) do if c.name=="eslint" then return true end end return false end)()',60)
            wait(nvim, '(function() for _,d in ipairs(vim.diagnostic.get(0)) do if d.code=="no-unused-vars" then return true end end return false end)()',60)
            nvim.current.buffer[:]=['const message={hello:"Maya"};','console.log(message);']
            nvim.exec_lua('require("conform").format({timeout_ms=5000})')
            assert nvim.current.buffer[0]=='const message = { hello: "Maya" };',nvim.current.buffer[:]
            print('PASS ESLint project: config-aware attachment, real lint diagnostic, Prettier formatting',flush=True)
        finally:
            stop(nvim)


if __name__ == '__main__':
    main()
    eslint_project()
