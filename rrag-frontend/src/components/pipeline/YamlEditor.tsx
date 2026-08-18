import Editor from '@monaco-editor/react';
import { usePipelineEditorStore } from '../../stores/pipeline-editor.store';
import { useRef, useCallback } from 'react';

export function YamlEditor() {
  const yamlSource = usePipelineEditorStore((s) => s.yamlSource);
  const yamlError = usePipelineEditorStore((s) => s.yamlError);
  const syncFromYaml = usePipelineEditorStore((s) => s.syncFromYaml);
  const syncSource = usePipelineEditorStore((s) => s.syncSource);
  const timerRef = useRef<number>(undefined);

  const handleChange = useCallback(
    (value: string | undefined) => {
      if (!value) return;
      clearTimeout(timerRef.current);
      timerRef.current = window.setTimeout(() => {
        syncFromYaml(value);
      }, 500);
    },
    [syncFromYaml]
  );

  return (
    <div className="h-full flex flex-col bg-surface-950">
      {yamlError && (
        <div className="px-3 py-1 bg-red-500/10 text-red-400 text-xs truncate border-b border-red-500/20">
          YAML Error: {yamlError}
        </div>
      )}
      {syncSource === 'yaml' && !yamlError && (
        <div className="px-3 py-0.5 bg-emerald-500/10 text-emerald-400 text-[10px] border-b border-emerald-500/20">
          Synced from YAML
        </div>
      )}
      <div className="flex-1">
        <Editor
          height="100%"
          language="yaml"
          value={yamlSource}
          onChange={handleChange}
          theme="vs-dark"
          options={{
            minimap: { enabled: false },
            fontSize: 13,
            wordWrap: 'on',
            scrollBeyondLastLine: false,
          }}
        />
      </div>
    </div>
  );
}
