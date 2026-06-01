import os
import json
import importlib
import sys

class ExtensionHost:
    """
    Registry host that acts as the service locator for loaded extensions.
    Provides tag verification and validation.
    """
    def __init__(self, extensions_dict):
        self._extensions = extensions_dict

    def get_extension(self, name: str = None, tags: list = None) -> object:
        if not name and not tags:
            raise ValueError("Either extension name or tags must be specified.")
            
        if name:
            ext = self._extensions.get(name)
            if not ext:
                raise ValueError(f"Required extension '{name}' is not loaded.")
            if tags:
                ext_tags = getattr(ext, "tags", [])
                for tag in tags:
                    if tag not in ext_tags:
                        raise ValueError(f"Extension '{name}' does not implement the required tag '{tag}'.")
            return ext
            
        # Match purely by tags
        matched_exts = []
        for ext in self._extensions.values():
            ext_tags = getattr(ext, "tags", [])
            if all(tag in ext_tags for tag in tags):
                matched_exts.append(ext)
                
        if not matched_exts:
            raise ValueError(f"No loaded extension implements all required tags: {tags}")
        if len(matched_exts) > 1:
            print(f"Warning: Multiple extensions match tags {tags}. Resolving to the first loaded: {matched_exts[0].__class__.__name__}")
        return matched_exts[0]

def load_extensions(core_config, host=None):
    """
    Dynamically loads portal extensions specified in core_config.EXTENSIONS
    """
    extensions = []
    
    # Ensure portal directory is in sys.path so 'servers' package can be imported
    if core_config.PORTAL_DIR not in sys.path:
        sys.path.insert(0, core_config.PORTAL_DIR)
    # Ensure root workspace is in sys.path for sibling imports if any
    if core_config.ROOT_DIR not in sys.path:
        sys.path.insert(0, core_config.ROOT_DIR)

    # Initialize registry for cross-extension queries
    core_config.LOADED_EXTENSIONS = {}

    # Use extensions list defined in config
    extension_list = getattr(core_config, "EXTENSIONS", [])

    for ext_info in extension_list:
        module_name = ext_info.get("module")
        class_name = ext_info.get("class")
        if not module_name or not class_name:
            continue
            
        try:
            # Dynamically import the module
            module = importlib.import_module(module_name)
            # Get the extension class
            ext_class = getattr(module, class_name)
            
            # Get extension specific config and instantiate class
            ext_config = ext_info.get("config", {})
            ext_instance = ext_class(core_config, ext_config)
            extensions.append(ext_instance)
            core_config.LOADED_EXTENSIONS[class_name] = ext_instance
            print(f"Dynamically loaded extension: {module_name}.{class_name}")
        except Exception as e:
            print(f"Warning: Failed to dynamically load extension '{module_name}': {e}")
            
    # Instantiate ExtensionHost and inject it into loaded extensions
    if host is None:
        host = ExtensionHost(core_config.LOADED_EXTENSIONS)
    core_config.EXTENSION_HOST = host

    for ext in extensions:
        ext.host = host

    return extensions
