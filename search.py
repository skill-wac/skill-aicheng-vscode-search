"""
对话搜索工具 —— 搜索 Claude Code 历史对话 JSONL 记录
用法: python search.py "<关键词>" [--limit 10] [--context 3] [--project <项目名>]
"""
import json
import os
import re
import sys
import glob
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

PROJECTS_BASE = os.path.expanduser("~/.claude/projects")


def get_jsonl_files(project_filter=None):
    files = []
    for root, dirs, filenames in os.walk(PROJECTS_BASE):
        dirs[:] = [d for d in dirs if d not in ('tool-results', 'memory', 'tasks')]
        for f in filenames:
            if f.endswith('.jsonl') and not f.startswith('.'):
                full_path = os.path.join(root, f)
                project = os.path.basename(root)
                if project_filter and project_filter.lower() not in project.lower():
                    continue
                size = os.path.getsize(full_path)
                files.append((full_path, project, size))
    files.sort(key=lambda x: -x[2])
    return files


def search_file(filepath, keyword, ctx_lines=2):
    """搜索单个文件，返回匹配及其上下文"""
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

            # 提取时间戳
            timestamp = record.get('timestamp', '')
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    timestamp = dt.strftime('%m-%d %H:%M')
                except Exception:
                    pass

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

            if not content or len(content) < 5:
                continue

            # 收集上下文行
            ctx_start = max(0, i - ctx_lines)
            ctx_end = min(len(lines), i + ctx_lines + 1)
            context_lines = []
            for j in range(ctx_start, ctx_end):
                try:
                    ctx_record = json.loads(lines[j])
                except json.JSONDecodeError:
                    continue
                ctx_content = ""
                if 'content' in ctx_record:
                    ctx_content = str(ctx_record['content'])
                elif 'message' in ctx_record and isinstance(ctx_record['message'], dict):
                    msg = ctx_record['message']
                    if 'content' in msg:
                        if isinstance(msg['content'], list):
                            ctx_content = ' '.join(
                                item.get('text', '') for item in msg['content']
                                if isinstance(item, dict)
                            )
                        else:
                            ctx_content = str(msg['content'])

                if ctx_content and len(ctx_content) > 5:
                    ctx_ts = ctx_record.get('timestamp', '')
                    if ctx_ts:
                        try:
                            dt = datetime.fromisoformat(ctx_ts.replace('Z', '+00:00'))
                            ctx_ts = dt.strftime('%m-%d %H:%M')
                        except Exception:
                            pass
                    is_match = (j == i)
                    context_lines.append({
                        'time': ctx_ts,
                        'text': ctx_content[:300],
                        'isMatch': is_match,
                    })

            # 生成截取摘要
            pos = content.lower().find(keyword_lower)
            start = max(0, pos - 80)
            end = min(len(content), pos + len(keyword) + 120)
            snippet = content[start:end]
            if start > 0:
                snippet = "..." + snippet
            if end < len(content):
                snippet = snippet + "..."

            matches.append({
                'file': filepath,
                'line': i + 1,
                'timestamp': timestamp,
                'type': record_type,
                'snippet': snippet,
                'context': context_lines,
            })

    return matches


def main():
    if len(sys.argv) < 2:
        print("用法: python search.py <关键词> [--limit N] [--context N] [--project 项目名]")
        sys.exit(1)

    keyword = sys.argv[1]
    limit = 10
    ctx = 2
    project_filter = None

    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == '--limit' and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])
            i += 2
        elif sys.argv[i] == '--context' and i + 1 < len(sys.argv):
            ctx = int(sys.argv[i + 1])
            i += 2
        elif sys.argv[i] == '--project' and i + 1 < len(sys.argv):
            project_filter = sys.argv[i + 1]
            i += 2
        else:
            i += 1

    print(f"SEARCH:{keyword}:{limit}")

    files = get_jsonl_files(project_filter)
    shown = 0

    for filepath, project, size in files:
        if shown >= limit:
            break

        matches = search_file(filepath, keyword, ctx)
        if not matches:
            continue

        session_id = os.path.splitext(os.path.basename(filepath))[0][:8]
        # 使用特殊分隔符以便解析
        print(f"GROUP:{project} ({session_id}...)|{filepath}")

        for m in matches[:limit - shown]:
            print(f"MATCH:{m['line']}|{m['timestamp']}|{m['snippet']}")
            for cl in m['context']:
                marker = ">>" if cl['isMatch'] else "  "
                print(f"CTX:{marker}|{cl['time']}|{cl['text']}")
            print("ENDMATCH")
            shown += 1
            if shown >= limit:
                break

    if shown == 0:
        print("NORESULTS")


if __name__ == '__main__':
    main()
