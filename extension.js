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
    let html = fs.readFileSync(htmlPath, 'utf-8');
    currentPanel.webview.html = html;

    currentPanel.webview.onDidReceiveMessage(async (msg) => {
        if (msg.type === 'search') {
            const results = await runSearch(context, msg.keyword, msg.limit || 20);
            currentPanel.webview.postMessage({ type: 'results', keyword: msg.keyword, results });
        }
    });

    if (keyword) {
        setTimeout(() => {
            if (currentPanel) currentPanel.webview.postMessage({ type: 'search', keyword });
        }, 500);
    }
}

function runSearch(context, keyword, limit) {
    return new Promise((resolve) => {
        const scriptPath = path.join(context.extensionPath, 'search.py');
        execFile('python', [scriptPath, keyword, '--limit', String(limit)], {
            maxBuffer: 10 * 1024 * 1024, timeout: 30000
        }, (error, stdout) => {
            if (error) {
                resolve([{ items: [{ time: '', text: '搜索出错: ' + error.message }] }]);
                return;
            }
            const results = [];
            let current = null;
            for (const line of stdout.split('\n')) {
                if (line.startsWith('━━━')) {
                    if (current && current.items.length > 0) results.push(current);
                    current = { session: line.replace(/━/g, '').trim(), items: [] };
                } else if (current && line.trim().match(/^\[\d/)) {
                    const m = line.match(/\[(.*?)\]\s*(.*)/);
                    if (m) current.items.push({ time: m[1], text: m[2] });
                }
            }
            if (current && current.items.length > 0) results.push(current);
            resolve(results);
        });
    });
}

function deactivate() {}
module.exports = { activate, deactivate };
