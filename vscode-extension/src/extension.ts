import * as vscode from 'vscode';

export function activate(context: vscode.ExtensionContext) {
    // 1. Status Bar Item showing active agent state
    const statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
    statusBar.text = "$(git-branch) AgentGit: Active";
    statusBar.tooltip = "Click to open AgentGit Web Dashboard";
    statusBar.command = "agentgit.dashboard";
    statusBar.show();
    context.subscriptions.push(statusBar);

    // 2. Command: Open Web Dashboard
    const dashboardCmd = vscode.commands.registerCommand('agentgit.dashboard', () => {
        const terminal = getOrCreateTerminal();
        terminal.show();
        terminal.sendText('agentgit ui');
        vscode.window.showInformationMessage('Starting AgentGit Web Dashboard at http://localhost:8585');
    });

    // 3. Command: Show Behavioral Diff
    const diffCmd = vscode.commands.registerCommand('agentgit.diff', async () => {
        const v1 = await vscode.window.showInputBox({ prompt: 'Enter baseline version (e.g. v1.0)' });
        if (!v1) return;
        const v2 = await vscode.window.showInputBox({ prompt: 'Enter comparison version (e.g. v2.0)' });
        if (!v2) return;

        const terminal = getOrCreateTerminal();
        terminal.show();
        terminal.sendText(`agentgit diff ${v1} ${v2}`);
    });

    // 4. Command: Lint Current Prompt File
    const lintCmd = vscode.commands.registerCommand('agentgit.lint', () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showWarningMessage('No active prompt file to lint.');
            return;
        }
        const filePath = editor.document.fileName;
        const terminal = getOrCreateTerminal();
        terminal.show();
        terminal.sendText(`agentgit lint "${filePath}"`);
    });

    // 5. Command: List Snapshots
    const listCmd = vscode.commands.registerCommand('agentgit.snapshots', () => {
        const terminal = getOrCreateTerminal();
        terminal.show();
        terminal.sendText('agentgit list');
    });

    context.subscriptions.push(dashboardCmd, diffCmd, lintCmd, listCmd);
}

function getOrCreateTerminal(): vscode.Terminal {
    const existing = vscode.window.terminals.find(t => t.name === 'AgentGit');
    if (existing) {
        return existing;
    }
    return vscode.window.createTerminal('AgentGit');
}

export function deactivate() {}
