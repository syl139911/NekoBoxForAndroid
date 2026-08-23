package io.nekohasekai.sagernet.ui.profile

import android.os.Bundle
import android.view.View
import androidx.preference.EditTextPreference
import androidx.preference.PreferenceCategory
import androidx.preference.PreferenceFragmentCompat
import androidx.preference.SwitchPreference
import io.nekohasekai.sagernet.database.DataStore
import io.nekohasekai.sagernet.database.ProfileManager
import io.nekohasekai.sagernet.fmt.http.HttpBean
import io.nekohasekai.sagernet.fmt.v2ray.StandardV2RayBean

class HttpSettingsActivity : StandardV2RaySettingsActivity() {
    override fun createEntity() = HttpBean()

    override fun PreferenceFragmentCompat.viewCreated(view: View, savedInstanceState: Bundle?) {
        // 标准偏好屏已由父类 createPreferences 建好；此处仅追加 HTTP 专属开关。
        // 不调用 super.viewCreated（基类为空实现），避免成员扩展函数的 super 限制。
        val screen = preferenceScreen
        for (i in 0 until screen.preferenceCount) {
            val cat = screen.getPreference(i)
            if (cat is PreferenceCategory) {
                if (findPreference<androidx.preference.Preference>("password")?.parent == cat) {
                    if (findPreference<androidx.preference.Preference>("path") == null) {
                        EditTextPreference(requireContext()).apply {
                            key = "path"
                            title = "Proxy Path"
                            summary = "CONNECT 目标追加路径 (如 @gw.alicdn.com)"
                            summaryProvider = EditTextPreference.SimpleSummaryProvider.getInstance()
                            text = DataStore.configurationStore.getString("path", "")
                            setOnPreferenceChangeListener { _, newValue ->
                                DataStore.configurationStore.putString("path", newValue as String)
                                true
                            }
                            cat.addPreference(this)
                        }
                        SwitchPreference(requireContext()).apply {
                            key = "delHost"
                            title = "Del Host"
                            summary = "CONNECT 请求不发送 Host header"
                            isChecked = DataStore.configurationStore.getBoolean("delHost", false)
                            setOnPreferenceChangeListener { _, newValue ->
                                DataStore.configurationStore.putBoolean("delHost", newValue as Boolean)
                                true
                            }
                            cat.addPreference(this)
                        }
                    }
                    break
                }
            }
        }
    }

    override suspend fun saveAndExit() {
        val delHost = DataStore.configurationStore.getBoolean("delHost", false)
        val path = DataStore.configurationStore.getString("path", "") ?: ""
        val editingId = DataStore.editingId
        if (editingId == 0L) {
            val bean = createEntity() as HttpBean
            bean.delHost = delHost
            bean.path = path
            ProfileManager.createProfile(DataStore.editingGroup, bean)
        } else {
            val entity = proxyEntity ?: run { finish(); return }
            val bean = entity.requireBean() as HttpBean
            bean.delHost = delHost
            bean.path = path
            ProfileManager.updateProfile(entity)
        }
        finish()
    }
}
