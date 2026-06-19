import os
import re

replacements = [
    (r'from backtest\.constants import', r'from utilities.AppConfig import'),
    (r'import backtest\.constants', r'import utilities.AppConfig'),
    (r'backtest\.constants', r'utilities.AppConfig'),
    
    (r'from backtest\.engine import', r'from core_engine.BacktestEngine import'),
    (r'import backtest\.engine', r'import core_engine.BacktestEngine'),
    (r'backtest\.engine', r'core_engine.BacktestEngine'),
    
    (r'from backtest\.metrics import', r'from core_engine.CalculateMetrics import'),
    (r'import backtest\.metrics', r'import core_engine.CalculateMetrics'),
    (r'backtest\.metrics', r'core_engine.CalculateMetrics'),
    
    (r'from backtest\.reporting import', r'from core_engine.GenerateReport import'),
    (r'import backtest\.reporting', r'import core_engine.GenerateReport'),
    (r'backtest\.reporting', r'core_engine.GenerateReport'),
    
    (r'from backtest\.strategy import', r'from core_engine.XnoEngine import'),
    (r'import backtest\.strategy', r'import core_engine.XnoEngine'),
    (r'backtest\.strategy', r'core_engine.XnoEngine'),
    
    (r'from xno_sdk\.engine import', r'from core_engine.XnoEngine import'),
    (r'import xno_sdk\.engine', r'import core_engine.XnoEngine'),
    (r'xno_sdk\.engine', r'core_engine.XnoEngine'),
    
    (r'from xno_sdk\.emulator import', r'from core_engine.PlatformEmulator import'),
    (r'import xno_sdk\.emulator', r'import core_engine.PlatformEmulator'),
    (r'xno_sdk\.emulator', r'core_engine.PlatformEmulator'),
    
    (r'from xno_sdk\.series import', r'from core_engine.RestrictedSeries import'),
    (r'import xno_sdk\.series', r'import core_engine.RestrictedSeries'),
    (r'xno_sdk\.series', r'core_engine.RestrictedSeries'),
    
    (r'from agent\.gemini_client import', r'from llm_clients.GeminiClient import'),
    (r'import agent\.gemini_client', r'import llm_clients.GeminiClient'),
    (r'agent\.gemini_client', r'llm_clients.GeminiClient'),
    
    (r'from agent\.deepseek_client import', r'from llm_clients.DeepseekClient import'),
    (r'import agent\.deepseek_client', r'import llm_clients.DeepseekClient'),
    (r'agent\.deepseek_client', r'llm_clients.DeepseekClient'),
    
    (r'from agent\.ollama_client import', r'from llm_clients.OllamaClient import'),
    (r'import agent\.ollama_client', r'import llm_clients.OllamaClient'),
    (r'agent\.ollama_client', r'llm_clients.OllamaClient'),
    
    (r'from agent\.pipeline import', r'from strategy_workflows.GenerateStrategies import'),
    (r'import agent\.pipeline', r'import strategy_workflows.GenerateStrategies'),
    (r'agent\.pipeline', r'strategy_workflows.GenerateStrategies'),
    
    (r'from agent\.auto_submit import', r'from strategy_workflows.SubmitStrategies import'),
    (r'import agent\.auto_submit', r'import strategy_workflows.SubmitStrategies'),
    (r'agent\.auto_submit', r'strategy_workflows.SubmitStrategies'),
    
    (r'from agent\.mcts_pipeline import', r'from strategy_workflows.RunMCTS import'),
    (r'import agent\.mcts_pipeline', r'import strategy_workflows.RunMCTS'),
    (r'agent\.mcts_pipeline', r'strategy_workflows.RunMCTS'),
    
    (r'from agent\.mcts_engine import', r'from strategy_workflows.MCTSEngine import'),
    (r'import agent\.mcts_engine', r'import strategy_workflows.MCTSEngine'),
    (r'agent\.mcts_engine', r'strategy_workflows.MCTSEngine'),
    
    (r'from agent\.portfolio import', r'from strategy_workflows.PortfolioManager import'),
    (r'import agent\.portfolio', r'import strategy_workflows.PortfolioManager'),
    (r'agent\.portfolio', r'strategy_workflows.PortfolioManager'),
    
    (r'from agent\.convert_legacy_ideas import', r'from strategy_workflows.ConvertLegacyIdeas import'),
    (r'import agent\.convert_legacy_ideas', r'import strategy_workflows.ConvertLegacyIdeas'),
    (r'agent\.convert_legacy_ideas', r'strategy_workflows.ConvertLegacyIdeas'),
    
    (r'from backtest\.optimizer_v2 import', r'from strategy_workflows.OptimizeV2 import'),
    (r'import backtest\.optimizer_v2', r'import strategy_workflows.OptimizeV2'),
    (r'backtest\.optimizer_v2', r'strategy_workflows.OptimizeV2'),
    
    (r'from agent\.templates', r'from utilities.templates'),
    (r'import agent\.templates', r'import utilities.templates'),
    (r'agent\.templates', r'utilities.templates'),
    
    (r'from agent\.prompts import', r'from utilities.Prompts import'),
    (r'import agent\.prompts', r'import utilities.Prompts'),
    (r'agent\.prompts', r'utilities.Prompts'),
    
    (r'from agent\.mcts_dimensions import', r'from strategy_workflows.MCTSDimensions import'),
    (r'import agent\.mcts_dimensions', r'import strategy_workflows.MCTSDimensions'),
    (r'agent\.mcts_dimensions', r'strategy_workflows.MCTSDimensions'),
    
    (r'from agent\.sandbox_prefixer import', r'from utilities.SandboxPrefixer import'),
    (r'import agent\.sandbox_prefixer', r'import utilities.SandboxPrefixer'),
    (r'agent\.sandbox_prefixer', r'utilities.SandboxPrefixer'),
    
    (r'agent\.util\.deepseek4free', r'utilities.deps.deepseek4free')
]

root_dir = r"f:\Projects\alpha_farm"
for folder, _, files in os.walk(root_dir):
    if '.git' in folder or 'venv' in folder or '__pycache__' in folder or 'results' in folder:
        continue
    for file in files:
        if file.endswith('.py'):
            path = os.path.join(folder, file)
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            new_content = content
            for old, new in replacements:
                new_content = re.sub(old, new, new_content)
            
            if new_content != content:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"Updated {path}")
