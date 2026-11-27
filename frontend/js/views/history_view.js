import { api } from "../api.js";
import { fmtTimeAction } from "../time.js";
const { ref, onMounted } = Vue;
export const HistoryView = {
  setup() {
    const items = ref([]); const err = ref(""); const timeline = ref(null);
    async function reload() {
      try {
        const res = await api("/api/history");
        items.value = res.items || [];
        timeline.value = res.timeline || null;
      } catch (e) { err.value = e.message || String(e); }
    }
    onMounted(reload);
    return { items, err, timeline, reload, fmtTimeAction };
  },
  template: `
  <div class="panel">
    <h2>变更历史</h2>
    <div class="err" v-if="err">{{ err }}</div>
    <p class="muted" v-if="timeline && !timeline.aligned">时间线存在错位，复核未通过。</p>
    <table>
      <thead><tr><th>时间动作</th><th>开关</th><th>环境</th><th>详情</th><th>操作者</th></tr></thead>
      <tbody>
        <tr v-for="it in items" :key="it.id">
          <td>{{ fmtTimeAction(it.created_at, it.action) }}</td><td>{{ it.flag_key || '-' }}</td><td>{{ it.env_code || '-' }}</td>
          <td>{{ it.detail }}</td><td>{{ it.actor }}</td>
        </tr>
      </tbody>
    </table>
    <button class="btn secondary" style="margin-top:0.7rem" @click="reload">刷新</button>
  </div>`
};
