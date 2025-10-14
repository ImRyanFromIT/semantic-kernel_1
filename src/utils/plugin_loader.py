'''
Plugin loader utility for Semantic Kernel prompt-based plugins.

This module handles loading and registering prompt-based plugins from the filesystem.
'''

import os
import json
from pathlib import Path
from typing import Optional

from semantic_kernel import Kernel
from semantic_kernel.functions import KernelArguments
from semantic_kernel.prompt_template import PromptTemplateConfig


def load_prompt_plugin(
    kernel: Kernel,
    plugin_name: str,
    plugin_path: str,
    function_name: Optional[str] = None
) -> None:
    '''
    Load a prompt-based plugin from a directory containing config.json and skprompt.txt.
    
    Args:
        kernel: Semantic Kernel instance to register the plugin with
        plugin_name: Name to register the plugin as
        plugin_path: Path to the plugin directory (containing config.json and skprompt.txt)
        function_name: Optional custom function name (defaults to plugin_name)
    
    Raises:
        FileNotFoundError: If plugin files are missing
        json.JSONDecodeError: If config.json is invalid
    '''
    plugin_dir = Path(plugin_path)
    config_file = plugin_dir / 'config.json'
    prompt_file = plugin_dir / 'skprompt.txt'
    
    # Verify files exist
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_file}")
    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_file}")
    
    # Load config
    with open(config_file, 'r', encoding='utf-8') as f:
        config_data = json.load(f)
    
    # Load prompt template
    with open(prompt_file, 'r', encoding='utf-8') as f:
        prompt_template = f.read()
    
    # Use function name or default to plugin name
    func_name = function_name or plugin_name
    
    # Create prompt template config
    template_config = PromptTemplateConfig(
        name=func_name,
        description=config_data.get('description', ''),
        template=prompt_template,
        execution_settings=config_data.get('execution_settings', {}),
    )
    
    # Create and register the function
    from semantic_kernel.functions import KernelFunction
    from semantic_kernel.functions import KernelPlugin
    
    function = KernelFunction.from_prompt(
        function_name=func_name,
        plugin_name=plugin_name,
        prompt_template_config=template_config,
    )
    
    # Create plugin with the function
    plugin = KernelPlugin(name=plugin_name, functions=[function])
    
    # Add to kernel
    kernel.add_plugin(plugin)
    
    print(f"[+] Loaded plugin: {plugin_name}.{func_name}")


def load_all_plugins(kernel: Kernel, base_path: Optional[str] = None) -> None:
    '''
    Load all plugins from the src/plugins directory.
    
    This function loads all standard plugins used by the system:
    - content_validation (input guardrails)
    - intent_detection
    - entity_extraction
    - query_classification (clarity)
    - response_generation (clarification_question)
    - semantic_reranking (LLM-based candidate reranking)
    
    Args:
        kernel: Semantic Kernel instance to register plugins with
        base_path: Optional base path for plugins (defaults to src/plugins)
    '''
    # Determine base path
    if base_path is None:
        # Assume we're running from project root
        current_dir = Path(__file__).parent.parent.parent
        base_path = current_dir / 'src' / 'plugins'
    else:
        base_path = Path(base_path)
    
    if not base_path.exists():
        raise FileNotFoundError(f"Plugins directory not found: {base_path}")
    
    print(f"[*] Loading plugins from: {base_path}")
    
    # Define plugins to load (plugin_name, plugin_path, function_name)
    plugins_to_load = [
        # Input validation
        ('content_validation', base_path / 'content_validation', 'content_validation'),
        
        # Intent and entity extraction
        ('intent_detection', base_path / 'intent_detection', 'detect_intent'),
        ('entity_extraction', base_path / 'entity_extraction', 'extract_entities'),
        
        # Query classification
        ('clarity_classifier', base_path / 'query_classification' / 'clarity', 'assess_clarity'),
        
        # Response generation
        ('clarification_generator', base_path / 'response_generation' / 'clarification_question', 'generate_clarification'),
        
        # Semantic reranking
        ('semantic_reranker', base_path / 'semantic_reranking' / 'semantic_reranking_SRM', 'semantic_reranking'),
    ]
    
    # Load each plugin
    loaded_count = 0
    for plugin_name, plugin_path, function_name in plugins_to_load:
        try:
            load_prompt_plugin(
                kernel=kernel,
                plugin_name=plugin_name,
                plugin_path=str(plugin_path),
                function_name=function_name
            )
            loaded_count += 1
        except Exception as e:
            print(f"[!] Failed to load plugin {plugin_name}: {e}")
    
    print(f"[+] Successfully loaded {loaded_count}/{len(plugins_to_load)} plugins")


async def invoke_plugin(
    kernel: Kernel,
    plugin_name: str,
    function_name: str,
    **kwargs
) -> str:
    '''
    Invoke a plugin function with the given arguments.
    
    Args:
        kernel: Semantic Kernel instance
        plugin_name: Name of the plugin
        function_name: Name of the function to invoke
        **kwargs: Arguments to pass to the function
    
    Returns:
        Result from the plugin as a string
    
    Raises:
        ValueError: If plugin or function not found
    '''
    # Get the plugin
    plugin = kernel.plugins.get(plugin_name)
    if plugin is None:
        raise ValueError(f"Plugin '{plugin_name}' not found in kernel")
    
    # Get the function
    function = plugin.get(function_name)
    if function is None:
        raise ValueError(f"Function '{function_name}' not found in plugin '{plugin_name}'")
    
    # Create kernel arguments
    arguments = KernelArguments(**kwargs)
    
    # Invoke the function
    result = await kernel.invoke(function, arguments)
    
    # Return the result as string
    return str(result).strip()

