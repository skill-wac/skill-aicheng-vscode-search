"""
对话搜索工具 —— 搜索 Claude Code 历史对话 JSONL 记录
用法: python search.py "<关键词>" [--limit 10] [--project <项目名>]
"""
import json
import os
import re
import sys
import glob
from datetime import datetime

# Windows UTF-8
sys.stdout.reconfigure(encoding='utf-8')

# Claude Code 对话存储根目录
PROJECTS_BASE = os.path.expanduser("~/.claude/projects")

def get_jsonl_files(project_filter=None):
    """获取所有 JSONL 文件"""
    files = []
    for root, dirs, filenames in os.walk(PROJECTS_BASE):
        # 跳过 tool-results 和 memory 目录
        dirs[:] = [d for d in dirs if d not in ('tool-results', 'memory', 'tasks')]
        for f in filenames:
            if f.endswith('.jsonl') and not f.startswith('.'):
                full_path = os.path.join(root, f)
                project = os.path.basename(root)
                if project_filter and project_filter.lower() not in project.lower():
                    continue
                size = os.path.getsize(full_path)
                files.append((full_path, project, size))
    # 按大小排序（大的文件通常有更多内容）
    files.sort(key=lambda x: -x[2])
    return files


def search_file(filepath, keyword, context_lines=1):
    """搜索单个文件"""
    matches = []
    try:
        with open(filepath, encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
    except Exception:
        return matches

    keyword_lower = keyword.lower()
    for i, line in enumerate(lines):
        if keyword_lower in line.lower():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            # 提取内容
            content = ""
            record_type = record.get('type', '?')

            if 'content' in record:
                content = str(record['content'])
            elif 'message' in record and isinstance(record['message'], dict):
                msg = record['message']
                if 'content' in msg:
                    if isinstance(msg['content'], list):
                        parts = []
                        for item in msg['content']:
                            if isinstance(item, dict) and 'text' in item:
                                parts.append(str(item['text']))
                        content = ' '.join(parts)
                    else:
                        content = str(msg['content'])
                elif 'tool_calls' in msg:
                    # 工具调用
                    pass

            if not content or len(content) < 10:
                continue

            # 截取匹配位置附近的文本
            pos = content.lower().find(keyword_lower)
            start = max(0, pos - 80)
            end = min(len(content), pos + len(keyword) + 120)
            snippet = content[start:end]
            if start > 0:
                snippet = "..." + snippet
            if end < len(content):
                snippet = snippet + "..."

            timestamp = record.get('timestamp', '')
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    timestamp = dt.strftime('%m-%d %H:%M')
                except Exception:
                    pass

            matches.append({
                'timestamp': timestamp,
                'type': record_type,
                'snippet': snippet,
                'line': i,
            })

    return matches


def main():
    if len(sys.argv) < 2:
        print("用法: python search.py <关键词> [--limit N] [--project 项目名]")
        print("示例: python search.py Voicebox --limit 10")
        sys.exit(1)

    keyword = sys.argv[1]
    limit = 10
    project_filter = None

    # 解析可选参数
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == '--limit' and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])
            i += 2
        elif sys.argv[i] == '--project' and i + 1 < len(sys.argv):
            project_filter = sys.argv[i + 1]
            i += 2
        else:
            i += 1

    print(f"[搜索] \"{keyword}\"")
    if project_filter:
        print(f"📁 范围: {project_filter}")
    print(f"📊 最多显示: {limit} 条")
    print()

    files = get_jsonl_files(project_filter)
    print(f"扫描 {len(files)} 个会话文件...")
    print()

    total_matches = 0
    shown = 0

    for filepath, project, size in files:
        if shown >= limit:
            break

        matches = search_file(filepath, keyword)
        if not matches:
            continue

        session_id = os.path.splitext(os.path.basename(filepath))[0][:8]
        print(f"━━━ {project} ({session_id}...) ━━━")
        for m in matches[:limit - shown]:
            ts = m['timestamp']
            print(f"  [{ts}] {m['snippet']}")
            print()
            shown += 1
            total_matches += 1
            if shown >= limit:
                break

    print(f"共找到 {total_matches} 条匹配（显示 {shown} 条）")

    if total_matches == 0:
        print()
        print("💡 提示：")
        print("  - 试试更短的关键词")
        print("  - 检查拼写")
        print("  - 使用 --project 缩小搜索范围")


if __name__ == '__main__':
    main()
