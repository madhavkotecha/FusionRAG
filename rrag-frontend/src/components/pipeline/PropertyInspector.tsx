import { useState, useEffect, useCallback, type ChangeEvent } from 'react';
import { usePipelineEditorStore } from '../../stores/pipeline-editor.store';
import { Settings, Trash2, ChevronDown, ChevronRight, Code } from 'lucide-react';
import client from '../../api/client';

// ─── JSON Schema → Form Field Rendering ──────────────────────────────────────

interface SchemaProperty {
  type?: string;
  default?: unknown;
  description?: string;
  enum?: string[];
  minimum?: number;
  maximum?: number;
  items?: { type?: string; enum?: string[] };
  ui_widget?: string;
  ui_advanced?: boolean;
  ui_group?: string;
  [key: string]: unknown;
}

interface ConfigSchema {
  type: string;
  properties?: Record<string, SchemaProperty>;
  required?: string[];
}

// ─── Component registry cache (loaded from API or inline) ────────────────────

// Import the component definitions from the palette's known types
// In production, these would be fetched from the API
const COMPONENT_SCHEMAS: Record<string, ConfigSchema> = {};

function getSchemaForComponent(componentType: string): ConfigSchema | null {
  return COMPONENT_SCHEMAS[componentType] || null;
}

// ─── Individual field components ─────────────────────────────────────────────

function StringField({
  name,
  prop,
  value,
  onChange,
}: {
  name: string;
  prop: SchemaProperty;
  value: unknown;
  onChange: (name: string, value: unknown) => void;
}) {
  if (prop.enum) {
    return (
      <select
        value={(value as string) ?? prop.default ?? ''}
        onChange={(e) => onChange(name, e.target.value)}
        className="w-full text-xs rounded-md px-2 py-1.5 border border-border-primary bg-surface-800 text-text-primary focus:outline-none focus:ring-1 focus:ring-accent-500"
      >
        {prop.enum.map((opt) => (
          <option key={opt} value={opt}>
            {opt}
          </option>
        ))}
      </select>
    );
  }

  if (prop.ui_widget === 'textarea') {
    return (
      <textarea
        value={(value as string) ?? prop.default ?? ''}
        onChange={(e) => onChange(name, e.target.value)}
        rows={3}
        className="w-full text-xs font-mono rounded-md px-2 py-1.5 border border-border-primary bg-surface-800 text-text-primary focus:outline-none focus:ring-1 focus:ring-accent-500 resize-y"
      />
    );
  }

  if (prop.ui_widget === 'password') {
    return (
      <input
        type="password"
        value={(value as string) ?? prop.default ?? ''}
        onChange={(e) => onChange(name, e.target.value)}
        className="w-full text-xs font-mono rounded-md px-2 py-1.5 border border-border-primary bg-surface-800 text-text-primary focus:outline-none focus:ring-1 focus:ring-accent-500"
      />
    );
  }

  return (
    <input
      type="text"
      value={(value as string) ?? prop.default ?? ''}
      onChange={(e) => onChange(name, e.target.value)}
      className="w-full text-xs font-mono rounded-md px-2 py-1.5 border border-border-primary bg-surface-800 text-text-primary focus:outline-none focus:ring-1 focus:ring-accent-500"
    />
  );
}

function NumberField({
  name,
  prop,
  value,
  onChange,
}: {
  name: string;
  prop: SchemaProperty;
  value: unknown;
  onChange: (name: string, value: unknown) => void;
}) {
  const isInteger = prop.type === 'integer';
  const numValue = value != null ? Number(value) : (prop.default as number | undefined);

  return (
    <div className="flex items-center gap-2">
      <input
        type="number"
        value={numValue ?? ''}
        min={prop.minimum}
        max={prop.maximum}
        step={isInteger ? 1 : 0.1}
        onChange={(e) => {
          const v = e.target.value;
          if (v === '') {
            onChange(name, prop.default);
          } else {
            onChange(name, isInteger ? parseInt(v, 10) : parseFloat(v));
          }
        }}
        className="flex-1 text-xs font-mono rounded-md px-2 py-1.5 border border-border-primary bg-surface-800 text-text-primary focus:outline-none focus:ring-1 focus:ring-accent-500"
      />
      {prop.minimum != null && prop.maximum != null && (
        <span className="text-[9px] text-text-muted whitespace-nowrap">
          {prop.minimum}–{prop.maximum}
        </span>
      )}
    </div>
  );
}

function BooleanField({
  name,
  prop,
  value,
  onChange,
}: {
  name: string;
  prop: SchemaProperty;
  value: unknown;
  onChange: (name: string, value: unknown) => void;
}) {
  const checked = value != null ? Boolean(value) : Boolean(prop.default);

  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(name, !checked)}
      className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
        checked ? 'bg-accent-500' : 'bg-surface-700'
      }`}
    >
      <span
        className={`inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform ${
          checked ? 'translate-x-[18px]' : 'translate-x-[3px]'
        }`}
      />
    </button>
  );
}

function ArrayField({
  name,
  prop,
  value,
  onChange,
}: {
  name: string;
  prop: SchemaProperty;
  value: unknown;
  onChange: (name: string, value: unknown) => void;
}) {
  const items = Array.isArray(value) ? value : (prop.default as string[]) ?? [];
  const [inputVal, setInputVal] = useState('');

  // If items have enum constraints, render as multi-select checkboxes
  if (prop.items?.enum) {
    return (
      <div className="flex flex-wrap gap-1.5">
        {prop.items.enum.map((opt) => {
          const selected = items.includes(opt);
          return (
            <button
              key={opt}
              type="button"
              onClick={() => {
                const next = selected
                  ? items.filter((i: string) => i !== opt)
                  : [...items, opt];
                onChange(name, next);
              }}
              className={`text-[10px] px-2 py-0.5 rounded-full border transition-colors ${
                selected
                  ? 'bg-accent-500/20 border-accent-500/50 text-accent-300'
                  : 'bg-surface-800 border-border-primary text-text-muted hover:text-text-secondary'
              }`}
            >
              {opt}
            </button>
          );
        })}
      </div>
    );
  }

  // Tag input for free-form arrays
  return (
    <div className="space-y-1">
      <div className="flex flex-wrap gap-1">
        {items.map((item: string, idx: number) => (
          <span
            key={idx}
            className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-surface-700 text-text-secondary border border-border-primary"
          >
            {String(item)}
            <button
              type="button"
              onClick={() => onChange(name, items.filter((_: string, i: number) => i !== idx))}
              className="text-text-muted hover:text-red-400"
            >
              ×
            </button>
          </span>
        ))}
      </div>
      <div className="flex gap-1">
        <input
          type="text"
          value={inputVal}
          onChange={(e: ChangeEvent<HTMLInputElement>) => setInputVal(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && inputVal.trim()) {
              e.preventDefault();
              onChange(name, [...items, inputVal.trim()]);
              setInputVal('');
            }
          }}
          placeholder="Type and press Enter"
          className="flex-1 text-xs rounded-md px-2 py-1 border border-border-primary bg-surface-800 text-text-primary focus:outline-none focus:ring-1 focus:ring-accent-500"
        />
      </div>
    </div>
  );
}

// ─── Field wrapper with label and description ────────────────────────────────

function FormField({
  name,
  prop,
  value,
  onChange,
  isRequired,
}: {
  name: string;
  prop: SchemaProperty;
  value: unknown;
  onChange: (name: string, value: unknown) => void;
  isRequired: boolean;
}) {
  const displayName = name
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <label className="text-[10px] font-medium text-text-muted uppercase tracking-wider">
          {displayName}
          {isRequired && <span className="text-red-400 ml-0.5">*</span>}
        </label>
        {prop.type === 'boolean' && (
          <BooleanField name={name} prop={prop} value={value} onChange={onChange} />
        )}
      </div>
      {prop.description && (
        <p className="text-[9px] text-text-muted/70 leading-tight">{prop.description}</p>
      )}
      {prop.type === 'string' && (
        <StringField name={name} prop={prop} value={value} onChange={onChange} />
      )}
      {(prop.type === 'integer' || prop.type === 'number') && (
        <NumberField name={name} prop={prop} value={value} onChange={onChange} />
      )}
      {prop.type === 'array' && (
        <ArrayField name={name} prop={prop} value={value} onChange={onChange} />
      )}
      {prop.type === 'object' && !prop.enum && (
        <textarea
          value={
            typeof value === 'string'
              ? value
              : JSON.stringify(value ?? prop.default ?? {}, null, 2)
          }
          onChange={(e) => {
            try {
              onChange(name, JSON.parse(e.target.value));
            } catch {
              // Keep raw text while editing
            }
          }}
          rows={3}
          className="w-full text-xs font-mono rounded-md px-2 py-1.5 border border-border-primary bg-surface-800 text-text-primary focus:outline-none focus:ring-1 focus:ring-accent-500 resize-y"
        />
      )}
    </div>
  );
}

// ─── Main PropertyInspector ──────────────────────────────────────────────────

export function PropertyInspector() {
  const { nodes, selectedNodeId, updateNodeConfig, removeNode } =
    usePipelineEditorStore();

  const selectedNode = nodes.find((n) => n.id === selectedNodeId);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showJsonEditor, setShowJsonEditor] = useState(false);
  const [jsonText, setJsonText] = useState('');
  const [jsonError, setJsonError] = useState<string | null>(null);
  const [schema, setSchema] = useState<ConfigSchema | null>(null);

  // Fetch schema for selected component type
  useEffect(() => {
    if (!selectedNode) {
      setSchema(null);
      return;
    }

    const componentType = selectedNode.data.componentType;

    // Try local cache first
    const cached = getSchemaForComponent(componentType);
    if (cached) {
      setSchema(cached);
      return;
    }

    // Fetch from API using authenticated client
    client.get(`/api/v1/components/${componentType}`)
      .then((resp) => {
        const data = resp.data;
        if (data?.config_schema) {
          const s = data.config_schema as ConfigSchema;
          COMPONENT_SCHEMAS[componentType] = s;
          setSchema(s);
        }
      })
      .catch(() => {
        // Fallback: no schema available, will show JSON editor
        setSchema(null);
      });
  }, [selectedNode]);

  // Sync JSON editor text when node changes
  useEffect(() => {
    if (selectedNode) {
      setJsonText(JSON.stringify(selectedNode.data.config, null, 2));
      setJsonError(null);
    }
  }, [selectedNode]);

  const handleFieldChange = useCallback(
    (name: string, value: unknown) => {
      if (!selectedNode) return;
      const newConfig = { ...selectedNode.data.config, [name]: value };
      updateNodeConfig(selectedNode.id, newConfig);
    },
    [selectedNode, updateNodeConfig]
  );

  const handleJsonApply = () => {
    if (!selectedNode) return;
    try {
      const config = JSON.parse(jsonText);
      updateNodeConfig(selectedNode.id, config);
      setJsonError(null);
    } catch (err) {
      setJsonError(err instanceof SyntaxError ? err.message : 'Invalid JSON');
    }
  };

  if (!selectedNode) {
    return (
      <div className="p-4 text-sm text-text-muted text-center mt-8">
        <Settings className="w-8 h-8 mx-auto mb-2 opacity-30" />
        Select a node to view its properties
      </div>
    );
  }

  const config = selectedNode.data.config;
  const properties = schema?.properties ?? {};
  const required = schema?.required ?? [];

  // Separate fields into standard and advanced
  const standardFields: [string, SchemaProperty][] = [];
  const advancedFields: [string, SchemaProperty][] = [];

  for (const [key, prop] of Object.entries(properties)) {
    if (prop.ui_advanced) {
      advancedFields.push([key, prop]);
    } else {
      standardFields.push([key, prop]);
    }
  }

  const hasSchema = standardFields.length > 0 || advancedFields.length > 0;

  return (
    <div className="p-4 space-y-4 bg-surface-900 overflow-y-auto">
      {/* Header info */}
      <h3 className="text-[10px] font-semibold text-text-muted uppercase tracking-widest">
        Properties
      </h3>
      <div className="space-y-2">
        <div>
          <label className="block text-[10px] font-medium text-text-muted mb-0.5 uppercase tracking-wider">
            Type
          </label>
          <div className="text-sm text-text-primary font-mono">
            {selectedNode.data.componentType}
          </div>
        </div>
        <div>
          <label className="block text-[10px] font-medium text-text-muted mb-0.5 uppercase tracking-wider">
            Category
          </label>
          <div className="text-sm text-text-primary">{selectedNode.data.category}</div>
        </div>
        <div>
          <label className="block text-[10px] font-medium text-text-muted mb-0.5 uppercase tracking-wider">
            Label
          </label>
          <div className="text-sm text-text-primary">{selectedNode.data.label}</div>
        </div>
      </div>

      {/* Schema-driven form fields */}
      {hasSchema && (
        <div className="border-t border-border-primary pt-3 space-y-3">
          <h4 className="text-[10px] font-semibold text-text-muted uppercase tracking-widest">
            Configuration
          </h4>

          {/* Standard fields */}
          <div className="space-y-3">
            {standardFields.map(([key, prop]) => (
              <FormField
                key={key}
                name={key}
                prop={prop}
                value={config[key]}
                onChange={handleFieldChange}
                isRequired={required.includes(key)}
              />
            ))}
          </div>

          {/* Advanced fields (collapsible) */}
          {advancedFields.length > 0 && (
            <div>
              <button
                type="button"
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="flex items-center gap-1.5 text-[10px] font-medium text-text-muted hover:text-text-secondary transition-colors uppercase tracking-wider"
              >
                {showAdvanced ? (
                  <ChevronDown className="w-3 h-3" />
                ) : (
                  <ChevronRight className="w-3 h-3" />
                )}
                Advanced ({advancedFields.length})
              </button>
              {showAdvanced && (
                <div className="mt-2 space-y-3 pl-2 border-l border-border-primary/50">
                  {advancedFields.map(([key, prop]) => (
                    <FormField
                      key={key}
                      name={key}
                      prop={prop}
                      value={config[key]}
                      onChange={handleFieldChange}
                      isRequired={required.includes(key)}
                    />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* JSON Editor toggle (always available as fallback) */}
      <div className="border-t border-border-primary pt-3">
        <button
          type="button"
          onClick={() => {
            setShowJsonEditor(!showJsonEditor);
            if (!showJsonEditor) {
              setJsonText(JSON.stringify(config, null, 2));
            }
          }}
          className="flex items-center gap-1.5 text-[10px] font-medium text-text-muted hover:text-text-secondary transition-colors uppercase tracking-wider"
        >
          <Code className="w-3 h-3" />
          {showJsonEditor ? 'Hide' : 'Show'} JSON Editor
        </button>

        {(showJsonEditor || !hasSchema) && (
          <div className="mt-2 space-y-2">
            <textarea
              value={jsonText}
              onChange={(e) => setJsonText(e.target.value)}
              rows={8}
              className={`w-full text-xs font-mono rounded-lg p-2.5 focus:outline-none focus:ring-2 focus:ring-accent-500 transition-colors ${
                jsonError
                  ? 'border border-red-500/50 bg-red-500/5 text-red-300'
                  : 'border border-border-primary bg-surface-800 text-text-primary'
              }`}
            />
            {jsonError && <p className="text-xs text-red-400">{jsonError}</p>}
            <button
              type="button"
              onClick={handleJsonApply}
              className="w-full bg-accent-500 text-white text-xs py-1.5 px-3 rounded-lg hover:bg-accent-400 transition-colors"
            >
              Apply JSON
            </button>
          </div>
        )}
      </div>

      {/* Delete button */}
      <div className="border-t border-border-primary pt-3">
        <button
          type="button"
          onClick={() => removeNode(selectedNode.id)}
          className="w-full flex items-center justify-center gap-1 bg-red-500/10 text-red-400 text-xs py-1.5 px-3 rounded-lg hover:bg-red-500/20 border border-red-500/20 transition-colors"
        >
          <Trash2 className="w-3 h-3" />
          Delete Node
        </button>
      </div>
    </div>
  );
}
