/**
 * Patched copy of react-native's jest/mockComponent.js.
 *
 * Upstream (node_modules/react-native/jest/mockComponent.js) crashes with
 * "Cannot read properties of undefined (reading 'constructor')" for any
 * native component that is declared as an arrow function (RN 0.81 uses
 * Flow's `component(...)` syntax for most core components, e.g.
 * ActivityIndicator, FlatList's internals, TextInput, etc.), because arrow
 * functions have no `.prototype`. This copy adds an optional-chaining guard
 * around that check so those components fall back to `React.Component`
 * instead of throwing. Wired in via moduleNameMapper in package.json.
 */
import * as React from 'react';
import {createElement} from 'react';
import path from 'path';

// `moduleName` is a path relative to node_modules/react-native/jest/mocks/
// (the original caller's directory), not relative to this file. Resolve it
// from there explicitly.
function resolveFromRNMocks(moduleName) {
  // Relative paths passed to mockComponent() are conventionally written
  // relative to node_modules/react-native/jest/mockComponent.js itself
  // (the module that originally calls jest.requireActual on them), not
  // relative to this patched copy's location.
  const rnJestDir = path.join(path.dirname(require.resolve('react-native/package.json')), 'jest');
  return path.resolve(rnJestDir, moduleName);
}

export default function mockComponent(moduleName, instanceMethods, isESModule) {
  const resolvedModuleName = resolveFromRNMocks(moduleName);
  const RealComponent = isESModule
    ? jest.requireActual(resolvedModuleName).default
    : jest.requireActual(resolvedModuleName);

  const SuperClass =
    typeof RealComponent === 'function' &&
    RealComponent.prototype?.constructor instanceof React.Component
      ? RealComponent
      : React.Component;

  const name =
    RealComponent.displayName ??
    RealComponent.name ??
    (RealComponent.render == null
      ? 'Unknown'
      : RealComponent.render.displayName ?? RealComponent.render.name);

  const nameWithoutPrefix = name.replace(/^(RCT|RK)/, '');

  const Component = class extends SuperClass {
    static displayName = 'Component';

    render() {
      const props = {...RealComponent.defaultProps};

      if (this.props) {
        Object.keys(this.props).forEach(prop => {
          if (this.props[prop] !== undefined) {
            props[prop] = this.props[prop];
          }
        });
      }

      return createElement(nameWithoutPrefix, props, this.props.children);
    }
  };

  Object.defineProperty(Component, 'name', {
    value: name,
    writable: false,
    enumerable: false,
    configurable: true,
  });

  Component.displayName = nameWithoutPrefix;

  Object.keys(RealComponent).forEach(classStatic => {
    Component[classStatic] = RealComponent[classStatic];
  });

  if (instanceMethods != null) {
    Object.assign(Component.prototype, instanceMethods);
  }

  return Component;
}
