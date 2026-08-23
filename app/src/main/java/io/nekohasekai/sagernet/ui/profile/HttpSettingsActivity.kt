package io.nekohasekai.sagernet.ui.profile

import android.os.Bundle
import android.view.View
import androidx.preference.EditTextPreference
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

    private val delHost = pbm.add(PreferenceBinding(Type.Bool, "delHost"))

    override fun PreferenceFragmentCompat.viewCreated(view: View, savedInstanceState: Bundle?) {
        val cat = findPreference<Preference>("serverPort")?.parent as? PreferenceCategory ?: return

        // 1. 动态创建 delHost（仅 HTTP 可见）
        if (findPreference<Preference>("delHost") == null) {
            SwitchPreference(requireContext()).apply {
                key = "delHost"
                title = "Del Host"
                summary = "CONNECT 请求不发送 Host header"
                cat.addPreference(this)
            }
        }

        // 2. 把 path 和 delHost 移到 serverPort 后面
        val pathPref = findPreference<Preference>("path") ?: return
        val delHostPref = findPreference<Preference>("delHost") ?: return
        val portPref = findPreference<Preference>("serverPort") ?: return

        // 暂存 path 和 delHost 后面的所有 preference
        val prefs = cat.preferences.toMutableList()
        val after = prefs.filter { it != pathPref && it != delHostPref && prefs.indexOf(it) > prefs.indexOf(portPref) }

        // 移除 path、delHost、以及 serverPort 后面的所有项
        cat.removePreference(pathPref)
        cat.removePreference(delHostPref)
        after.forEach { cat.removePreference(it) }

        // 按正确顺序加回来：serverPort → path → delHost → 原来后面的项
        cat.addPreference(pathPref)
        cat.addPreference(delHostPref)
        after.forEach { cat.addPreference(it) }
    }
}
