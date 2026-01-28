#!/usr/bin/env python3
"""
Migrate emoji icons to Heroicons in templates.

This script replaces emoji characters with Jinja macro calls to the icon system.
Run with --dry-run first to see what changes would be made.

Usage:
    python scripts/migrate_emojis_to_icons.py --dry-run  # Preview changes
    python scripts/migrate_emojis_to_icons.py            # Apply changes
    python scripts/migrate_emojis_to_icons.py --report   # Generate report only
"""

import re
import argparse
from pathlib import Path
from typing import Dict, List, Tuple
import json

# Emoji to Heroicon mapping
# Format: emoji -> (icon_name, size)
EMOJI_MAPPING: Dict[str, Tuple[str, str]] = {
    # Money/Finance
    '💰': ('banknotes', 'md'),
    '💵': ('banknotes', 'md'),
    '💲': ('currency-dollar', 'md'),
    '💳': ('credit-card', 'md'),
    '🏦': ('building-office', 'md'),

    # Charts/Analytics
    '📊': ('chart-bar', 'md'),
    '📈': ('arrow-trending-up', 'md'),
    '📉': ('arrow-trending-up', 'md'),  # Could use arrow-trending-down if available

    # Tips/Ideas
    '💡': ('light-bulb', 'md'),
    '✨': ('sparkles', 'md'),
    '⭐': ('star', 'md'),
    '🌟': ('star', 'md'),

    # Success/Validation
    '✓': ('check', 'md'),
    '✅': ('check-circle', 'md'),
    '☑️': ('check-circle', 'md'),
    '✔️': ('check', 'md'),

    # Error/Warning
    '❌': ('x-circle', 'md'),
    '✕': ('x-mark', 'md'),
    '⚠️': ('exclamation-triangle', 'md'),
    '⚠': ('exclamation-triangle', 'md'),
    '🚫': ('x-circle', 'md'),
    '❗': ('exclamation-circle', 'md'),
    '❓': ('question-mark-circle', 'md'),

    # Documents/Files
    '📋': ('clipboard-document-list', 'md'),
    '📄': ('document-text', 'md'),
    '📃': ('document-text', 'md'),
    '📝': ('pencil', 'md'),
    '📁': ('folder', 'md'),
    '📂': ('folder', 'md'),
    '🗂️': ('folder', 'md'),

    # Communication
    '📧': ('envelope', 'md'),
    '📨': ('envelope', 'md'),
    '✉️': ('envelope', 'md'),
    '📞': ('phone', 'md'),
    '☎️': ('phone', 'md'),
    '📱': ('phone', 'md'),

    # People
    '👤': ('user', 'md'),
    '👥': ('users', 'md'),
    '🧑': ('user', 'md'),
    '👨': ('user', 'md'),
    '👩': ('user', 'md'),

    # Buildings/Places
    '🏠': ('home', 'md'),
    '🏡': ('home', 'md'),
    '🏢': ('building-office', 'md'),
    '🏛️': ('building-office', 'md'),

    # Settings/Tools
    '⚙️': ('cog-6-tooth', 'md'),
    '🔧': ('cog-6-tooth', 'md'),
    '🛠️': ('cog-6-tooth', 'md'),
    '🔨': ('cog-6-tooth', 'md'),

    # Security
    '🔐': ('lock-closed', 'md'),
    '🔒': ('lock-closed', 'md'),
    '🔓': ('lock-closed', 'md'),  # Could differentiate if lock-open is available
    '🛡️': ('shield-check', 'md'),
    '🔑': ('key', 'md'),

    # Actions
    '➕': ('plus', 'md'),
    '➖': ('minus', 'md'),
    '✏️': ('pencil', 'md'),
    '🗑️': ('trash', 'md'),
    '🔍': ('magnifying-glass', 'md'),
    '🔎': ('magnifying-glass', 'md'),

    # Arrows/Navigation
    '➡️': ('arrow-right', 'md'),
    '⬅️': ('arrow-left', 'md'),
    '⬆️': ('chevron-up', 'md'),
    '⬇️': ('chevron-down', 'md'),
    '↗️': ('arrow-trending-up', 'md'),
    '🔄': ('arrow-path', 'md'),

    # Time
    '📅': ('calendar', 'md'),
    '🗓️': ('calendar', 'md'),
    '⏰': ('clock', 'md'),
    '🕐': ('clock', 'md'),
    '⏱️': ('clock', 'md'),

    # Misc
    '🔔': ('bell', 'md'),
    '🔕': ('bell', 'md'),
    '❤️': ('heart', 'md'),
    '🌐': ('globe-alt', 'md'),
    '🖨️': ('printer', 'md'),
    '📤': ('arrow-up-tray', 'md'),
    '📥': ('arrow-down-tray', 'md'),
    '👁️': ('eye', 'md'),
    '👁': ('eye', 'md'),
    '📌': ('star', 'md'),
    '🔗': ('arrow-right', 'md'),
    '⏳': ('clock', 'md'),
    '⌛': ('clock', 'md'),
    '🎯': ('sparkles', 'md'),
    '🚀': ('arrow-trending-up', 'md'),
    '💼': ('building-office', 'md'),
    '🎁': ('sparkles', 'md'),
    '📖': ('document-text', 'md'),
    '📚': ('clipboard-document-list', 'md'),
    '🧮': ('calculator', 'md'),
    '📑': ('document-text', 'md'),
    '🏷️': ('star', 'md'),
    '✍️': ('pencil', 'md'),
    '🖊️': ('pencil', 'md'),
    '📬': ('envelope', 'md'),
    '📩': ('envelope', 'md'),
}


def find_emojis(content: str) -> List[Tuple[str, int, int]]:
    """
    Find all emojis in content with their positions.
    Returns list of (emoji, start, end) tuples.
    """
    # Unicode emoji pattern
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F700-\U0001F77F"  # alchemical symbols
        "\U0001F780-\U0001F7FF"  # Geometric Shapes
        "\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
        "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
        "\U0001FA00-\U0001FA6F"  # Chess Symbols
        "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
        "\U00002702-\U000027B0"  # Dingbats
        "\U000024C2-\U0001F251"
        "✓✕✔☑⚠❌❗❓⚙☎✉➕➖➡⬅⬆⬇↗✏"  # Common text symbols
        "]+",
        flags=re.UNICODE
    )

    matches = []
    for match in emoji_pattern.finditer(content):
        matches.append((match.group(), match.start(), match.end()))

    return matches


def generate_icon_call(emoji: str, mapping: Dict[str, Tuple[str, str]]) -> str:
    """Generate the Jinja2 icon macro call for an emoji."""
    if emoji in mapping:
        icon_name, size = mapping[emoji]
        return f"{{{{ icon('{icon_name}') }}}}"
    return emoji  # Return original if not mapped


def migrate_file(filepath: Path, dry_run: bool = True, verbose: bool = False) -> Dict:
    """
    Migrate emojis to icons in a single file.
    Returns dict with stats.
    """
    try:
        content = filepath.read_text(encoding='utf-8')
    except Exception as e:
        return {'error': str(e), 'path': str(filepath)}

    original = content
    replacements = []

    # Find and replace emojis
    for emoji in EMOJI_MAPPING:
        if emoji in content:
            icon_call = generate_icon_call(emoji, EMOJI_MAPPING)
            count = content.count(emoji)
            if count > 0:
                replacements.append({
                    'emoji': emoji,
                    'icon': icon_call,
                    'count': count
                })
                content = content.replace(emoji, icon_call)

    # Check if we need to add the import
    if replacements and "{% from 'macros/icons.html' import icon %}" not in content:
        # Find the best place to add the import
        # After {% extends %} if present, otherwise at the top
        extends_match = re.search(r'{% extends ["\'][^"\']+["\'] %}', content)
        if extends_match:
            insert_pos = extends_match.end()
            content = content[:insert_pos] + "\n{% from 'macros/icons.html' import icon %}" + content[insert_pos:]
        else:
            content = "{% from 'macros/icons.html' import icon %}\n" + content

    # Write changes if not dry run
    if content != original and not dry_run:
        filepath.write_text(content, encoding='utf-8')

    return {
        'path': str(filepath),
        'modified': content != original,
        'replacements': replacements,
        'total_replacements': sum(r['count'] for r in replacements)
    }


def generate_report(results: List[Dict]) -> str:
    """Generate a markdown report of the migration."""
    report = []
    report.append("# Emoji to Icon Migration Report\n")
    report.append(f"Total files scanned: {len(results)}")

    modified = [r for r in results if r.get('modified', False)]
    errors = [r for r in results if 'error' in r]

    report.append(f"Files to modify: {len(modified)}")
    report.append(f"Files with errors: {len(errors)}")
    report.append("")

    if modified:
        report.append("## Files to Modify\n")
        total_replacements = 0

        for result in modified:
            report.append(f"### {result['path']}")
            report.append(f"Total replacements: {result['total_replacements']}")
            report.append("")
            report.append("| Emoji | Icon | Count |")
            report.append("|-------|------|-------|")

            for r in result['replacements']:
                report.append(f"| {r['emoji']} | `{r['icon']}` | {r['count']} |")
                total_replacements += r['count']

            report.append("")

        report.append(f"\n**Total emoji replacements: {total_replacements}**\n")

    if errors:
        report.append("## Errors\n")
        for result in errors:
            report.append(f"- {result['path']}: {result['error']}")

    return "\n".join(report)


def main():
    parser = argparse.ArgumentParser(
        description='Migrate emoji icons to Heroicons in templates'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without modifying files'
    )
    parser.add_argument(
        '--report',
        action='store_true',
        help='Generate markdown report only'
    )
    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Show detailed output'
    )
    parser.add_argument(
        '--path',
        type=str,
        default='src/web/templates',
        help='Path to templates directory'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Output file for report (default: stdout)'
    )

    args = parser.parse_args()

    # Find all template files
    templates_dir = Path(args.path)
    if not templates_dir.exists():
        print(f"Error: Directory not found: {templates_dir}")
        return 1

    template_files = list(templates_dir.rglob('*.html'))

    if not template_files:
        print(f"No HTML files found in {templates_dir}")
        return 0

    print(f"Scanning {len(template_files)} template files...")

    # Process files
    results = []
    for filepath in template_files:
        result = migrate_file(filepath, dry_run=args.dry_run or args.report, verbose=args.verbose)
        results.append(result)

        if args.verbose and result.get('modified'):
            print(f"  Modified: {filepath} ({result['total_replacements']} replacements)")

    # Generate report
    report = generate_report(results)

    if args.output:
        Path(args.output).write_text(report)
        print(f"Report written to {args.output}")
    else:
        print("\n" + report)

    # Summary
    modified_count = len([r for r in results if r.get('modified', False)])

    if args.dry_run:
        print(f"\n[DRY RUN] {modified_count} files would be modified.")
        print("Run without --dry-run to apply changes.")
    elif not args.report:
        print(f"\n{modified_count} files modified.")

    return 0


if __name__ == '__main__':
    exit(main())
