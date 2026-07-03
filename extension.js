const vscode = require('vscode');
const { execFile } = require('child_process');
const path = require('path');
const fs = require('fs');

let currentPanel = undefined;

function activate(context) {
    vscode.window.showInformationMessage('skill&爱成 已启动！Ctrl+Alt+F 搜索对话。');

    const searchCmd = vscode.commands.registerCommand('skill-aicheng.search', async () => {
        const keyword = await vscode.window.showInputBox({
            prompt: '输入关键词搜索历史对话',
            placeHolder: '例如：检定台、Voicebox、风险...',
            title: 'skill&爱成 - 对话搜索'
        });
        if (!keyword) return;
        openSearchPanel(context, keyword);
    });

    const statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    statusBar.text = '$(search) skill&爱成';
    statusBar.tooltip = '搜索历史对话 (Ctrl+Alt+F)';
    statusBar.command = 'skill-aicheng.search';
    statusBar.color = '#89b4fa';
    statusBar.show();

    context.subscriptions.push(searchCmd, statusBar);
}

function openSearchPanel(context, keyword) {
    if (currentPanel) {
        currentPanel.reveal();
        if (keyword) currentPanel.webview.postMessage({ type: 'search', keyword });
        return;
    }

    currentPanel = vscode.window.createWebviewPanel(
        'skillAichengSearch',
        'skill&爱成 - 对话搜索',
        vscode.ViewColumn.Beside,
        { enableScripts: true, retainContextWhenHidden: true }
    );

    currentPanel.onDidDispose(() => { currentPanel = undefined; });

    const htmlPath = path.join(context.extensionPath, 'media', 'search.html');
    currentPanel.webview.html = fs.readFileSync(htmlPath, 'utf-8');

    currentPanel.webview.onDidReceiveMessage(async (msg) => {
        if (msg.type === 'search') {
            const results = await doSearch(context, msg.keyword, msg.limit || 20, 2);
            currentPanel.webview.postMessage({ type: 'results', keyword: msg.keyword, results });
        } else if (msg.type === 'expandContext') {
            const results = await doSearch(context, msg.keyword, 1, msg.contextLines || 10);
            currentPanel.webview.postMessage({ type: 'expandedContext', results });
        }
    });

    if (keyword) {
        setTimeout(() => {
            if (currentPanel) currentPanel.webview.postMessage({ type: 'search', keyword });
        }, 500);
    }
}

function doSearch(context, keyword, limit, ctxLines) {
    return new Promise((resolve) => {
        const scriptPath = path.join(context.extensionPath, 'search.py');
        execFile('python', [scriptPath, keyword, '--limit', String(limit), '--context', String(ctxLines)], {
            maxBuffer: 10 * 1024 * 1024, timeout: 30000
        }, (error, stdout) => {
            if (error) {
                resolve([{ error: '搜索出错: ' + error.message }]);
                return;
            }
            resolve(parseOutput(stdout));
        });
    });
}

function parseOutput(stdout) {
    const results = [];
    let current = null;
    for (const line of stdout.split('\n')) {
        if (line.startsWith('GROUP:')) {
            if (current && current.matches && current.matches.length > 0) results.push(current);
            const parts = line.substring(6).split('|');
            current = { session: parts[0], file: parts[1] || '', matches: [] };
        } else if (line.startsWith('MATCH:') && current) {
            const parts = line.substring(6).split('|');
            current.matches.push({ line: parseInt(parts[0]) || 1, time: parts[1] || '', snippet: parts.slice(2).join('|'), context: [] });
        } else if (line.startsWith('CTX:') && current && current.matches.length > 0) {
            const last = current.matches[current.matches.length - 1];
            const parts = line.substring(4).split('|');
            last.context.push({ marker: parts[0], time: parts[1] || '', text: parts.slice(2).join('|') });
        }
    }
    if (current && current.matches && current.matches.length > 0) results.push(current);
    if (results.length === 0 && !stdout.includes('NORESULTS')) {
        return [{ error: '未找到匹配' }];
    }
    return results;
}

function deactivate() {}
module.exports = { activate, deactivate };
