<script lang="ts">
  import type { CommandRequest } from '../../api/control_api.js';
  import { statusBadgeClass } from './format.js';

  let { cmds }: { cmds: CommandRequest[] } = $props();
</script>

<div class="table-wrap card bg-surface-100-900 overflow-x-auto">
  <table class="table">
    <thead>
      <tr>
        <th>ID</th><th>Op</th><th>Source</th><th>Target</th>
        <th>Status</th><th>Created</th><th>Completed</th><th>Result</th>
      </tr>
    </thead>
    <tbody>
      {#if cmds.length === 0}
        <tr><td colspan="8" class="text-surface-600-400">No commands yet.</td></tr>
      {:else}
        {#each cmds as command (command.id)}
          <tr>
            <td><code class="font-mono">{command.id.substring(0, 8)}</code></td>
            <td>{command.operation_id}</td>
            <td>{command.source_device_id}</td>
            <td>{command.target_device_id}</td>
            <td>
              <span class={statusBadgeClass(command.status)}>
                {command.status}
              </span>
            </td>
            <td>{(command.created_at || '').toString().substring(0, 19)}</td>
            <td>{(command.finished_at || '').toString().substring(0, 19)}</td>
            <td>
              <code class="font-mono">
                {JSON.stringify(command.result || command.error || '').substring(0, 60)}
              </code>
            </td>
          </tr>
        {/each}
      {/if}
    </tbody>
  </table>
</div>
