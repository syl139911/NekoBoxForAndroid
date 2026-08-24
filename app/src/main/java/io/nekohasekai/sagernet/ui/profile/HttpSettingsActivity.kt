package io.nekohasekai.sagernet.ui.profile

import android.os.Bundle
import android.view.View
import androidx.preference.Preference
import androidx.preference.PreferenceCategory
import androidx.preference.PreferenceFragmentCompat
import androidx.preference.SwitchPreference
import io.nekohasekai.sagernet.R
import io.nekohasekai.sagernet.fmt.http.HttpBean
import moe.matsuri.nb4a.proxy.PreferenceBinding
import moe.matsuri.nb4a.proxy.Type

class HttpSettingsActivity : StandardV2RaySettingsActivity() {

    override fun createEntity() = HttpBean()

    // pbm.add() 只注册绑定到列表，不读写 preference
    // 实际读（writeToCacheAll）在 init()，写（fromCacheAll）在 serialize()，都是 bean 就绪之后
    private val delHost = pbm.add(PreferenceBinding(Type.Bool, "delHost"))

    override fun PreferenceFragmentCompat.viewCreated(view: View, savedInstanceState: Bundle?) {
        val cat = findPreference<Preference>("serverPort")?.parent as? PreferenceCategory ?: return

        // 1. 动态创建 delHost SwitchPreference（仅 HTTP 可见）
        if (findPreference<Preference>("delHost") == null) {
            SwitchPreference(requireContext()).apply {
                key = "delHost"
                title = getString(R.string.del_host)
                summary = getString(R.string.del_host_sum)
                cat.addPreference(this)
            }
        }

        // 2. 用 order 重排：serverPort → path → delHost → 其余
        //    避免 removePreference + addPreference（可能丢失 listener / 焦点状态）
        findPreference<Preference>("serverPort")?.order = 1
        findPreference<Preference>("path")?.order = 2
        findPreference<Preference>("delHost")?.order = 3
        // 其余 preference 保持 XML 默认 order（1000+），不影响排序
    }
}
