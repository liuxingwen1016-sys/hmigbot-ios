"""Synchronize discovery metadata from maintained Markdown without rewriting skills."""
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from hmigbot_ios import __version__


def main():
    skills = {}
    for path in sorted((ROOT / 'skills').glob('*/SKILL.md')):
        name = path.parent.name
        text = path.read_text(encoding='utf-8-sig')
        match = re.match(r'^---\n(.*?)\n---\n', text, re.S)
        if not match:
            raise ValueError('Missing skill frontmatter: ' + name)
        fields = dict(re.findall(r'^(name|description):\s*(.+)$', match[1], re.M))
        if fields.get('name') != name or not fields.get('description'):
            raise ValueError('Missing skill identity: ' + name)
        description = fields['description']
        if description in {'|', '>', '|-', '>-'}:
            parts = []
            for line in match[1].split('description:', 1)[1].splitlines()[1:]:
                if line and not line[0].isspace():
                    break
                parts.append(line.strip())
            description = ' '.join(parts)
        skills[name] = json.loads(description) if description.startswith('"') else description
    path = ROOT / 'src/hmigbot_ios/capabilities.json'
    catalog = json.loads(path.read_text(encoding='utf-8'))
    for atom in catalog['atoms']:
        atom['skill'] = {'A': 'ios-source-analysis', 'B': 'ios-source-analysis', 'C': 'ios-source-analysis', 'D': 'a2h-plan', 'E': 'a2h-execute', 'F': 'a2h-verify'}[atom['id'][0]]
        atom['status'] = 'checklist_reference'
        atom['execution_mode'] = 'original_a2h_pipeline_with_ios_source'
    catalog.update({'tool_version': __version__, 'public_skills': list(skills),
        'note': 'Original a2h pipeline with bundled HMigBot resources; 62 atoms are internal reference only.',
        'pipeline': ['a2h-spec', 'a2h-plan', 'a2h-execute', 'a2h-verify', 'a2h-retrospect']})
    catalog.pop('hmigbot_routes', None)
    path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    lines = ['# 完整HMigBot-iOS技能目录', '', '原a2h五阶段为唯一主线。技能、参考、模板、脚本和编译资源均已随包复制；同步脚本只更新索引，不写技能正文。', '']
    lines += [f'- [{name}](../skills/{name}/SKILL.md)：{description}' for name, description in skills.items()]
    lines += ['', '主控为a2h-run；iOS新增源分析、页面转换和资源前置能力，目标侧复用原领域技能。',
              '62项原子清单保留在src/hmigbot_ios/capabilities.json，不能用数量表示完成度。',
              '', '[原架构核对与改造](HMIGBOT-ARCHITECTURE-AUDIT.md)', '']
    (ROOT / 'docs/SKILLS.md').write_text('\n'.join(lines), encoding='utf-8', newline='\n')
    print(f'Catalog synchronized from {len(skills)} maintained skills; skill bodies untouched')


if __name__ == '__main__':
    main()
