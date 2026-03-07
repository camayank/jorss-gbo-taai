/**
 * Helper to load browser-targeted JS files that use `window.*` globals.
 * Simulates a browser environment for testing by providing a `window` object
 * and evaluating the source file in that context.
 */
var fs = require('fs');
var path = require('path');
var vm = require('vm');

function loadModule(filePath) {
  var absPath = path.resolve(filePath);
  var code = fs.readFileSync(absPath, 'utf-8');

  // Create a sandbox with window and module.exports
  var sandbox = {
    window: { location: { hostname: 'localhost' } },
    module: { exports: {} },
    exports: {},
    console: console,
    Object: Object,
    Array: Array,
    Proxy: Proxy,
    Set: Set,
    Map: Map,
    require: function(relPath) {
      // Resolve relative requires from the source file's directory
      var dir = path.dirname(absPath);
      return loadModule(path.resolve(dir, relPath));
    }
  };

  vm.runInNewContext(code, sandbox, { filename: absPath });

  // Return the module.exports (CJS path) or fall back to window globals
  if (Object.keys(sandbox.module.exports).length > 0) {
    return sandbox.module.exports;
  }
  // Collect all window.* assignments
  return sandbox.window;
}

module.exports = loadModule;
