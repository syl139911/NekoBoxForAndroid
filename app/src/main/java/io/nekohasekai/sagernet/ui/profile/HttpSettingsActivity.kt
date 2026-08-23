package io.nekohasekai.sagernet.ui.profile

import android.os.Bundle
import androidx.preference.PreferenceCategory
import androidx.preference.PreferenceFragmentCompat
import androidx.preference.SwitchPreference
import io.nekohasekai.sagernet.fmt.http.HttpBean
import io.nekohasekai.sagernet.fmt.v2ray.StandardV2RayBean

class HttpSettingsActivity : StandardV2RaySettingsActivity() {

    override fun createEntity() = HttpBean()

    override fun StandardV2RayBean.init() {}

    override fun StandardV2RayBean.serialize() {}

    override fun PreferenceFragmentCompat.createPreferences(
        savedInstanceState: Bundle?,
        rootKey: String?,
    ) {
        super.createPreferences(savedInstanceState, rootKey)

        // KunBox: 在 proxy category 里加 delHost 开关
        val screen = preferenceScreen
        for (i in 0 until screen.preferenceCount) {
            val cat = screen.getPreference(i)
            if (cat is PreferenceCategory) {
                if (findPreference<androidx.preference.Preference>("password")?.parent == cat) {
                    SwitchPreference(requireContext()).apply {
                        key = "kunboxDelHost"
                        title = "Del Host"
                        summary = "CONNECT 请求不发送 Host header"
                        isChecked = false
                        cat.addPreference(this)
                    }
                    break
                }
            }
        }
    }
}
