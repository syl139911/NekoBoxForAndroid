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

        // 2. 用 order 重排所有 preference
        //    Android DEFAULT_ORDER = 1000，必须给所有 preference 设明确值才能控制顺序
        //    目标：name → serverAddress → serverPort → path → delHost → username → password → ...
        var order = 0
        findPreference<Preference>("name")?.order = order++
        findPreference<Preference>("serverAddress")?.order = order++
        findPreference<Preference>("serverPort")?.order = order++
        findPreference<Preference>("path")?.order = order++        // 紧跟 serverPort
        findPreference<Preference>("delHost")?.order = order++      // 紧跟 path
        findPreference<Preference>("username")?.order = order++
        findPreference<Preference>("password")?.order = order++
        findPreference<Preference>("uuid")?.order = order++
        findPreference<Preference>("alterId")?.order = order++
        findPreference<Preference>("encryption")?.order = order++
        findPreference<Preference>("packetEncoding")?.order = order++
        findPreference<Preference>("type")?.order = order++
        findPreference<Preference>("host")?.order = order++
        findPreference<Preference>("security")?.order = order++
    }
}
