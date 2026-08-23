package io.nekohasekai.sagernet.ui.profile

import android.os.Bundle
import android.view.View
import androidx.preference.EditTextPreference
import androidx.preference.PreferenceCategory
import androidx.preference.PreferenceFragmentCompat
import androidx.preference.SwitchPreference
import io.nekohasekai.sagernet.R
import io.nekohasekai.sagernet.database.DataStore
import io.nekohasekai.sagernet.database.ProfileManager
import io.nekohasekai.sagernet.fmt.http.HttpBean

class HttpSettingsActivity : StandardV2RaySettingsActivity() {

    override fun createEntity() = HttpBean()

    override fun PreferenceFragmentCompat.viewCreated(view: View, savedInstanceState: Bundle?) {
        // 父类 createPreferences 已通过 R.xml.standard_v2ray_preferences 建好标准 preference，
        // 其中 key="path" 的 EditTextPreference 已存在。
        // 此处仅：1) 将 path 设为可见（HTTP 类型需要）；2) 配置 summaryProvider 和 changeListener；
        // 3) 追加 delHost 开关。

        // —— path preference（父类标准 preference key="path"，EditTextPreference）——
        val pathPref = findPreference<EditTextPreference>("path")
        if (pathPref != null) {
            // HTTP 类型的 path 即 CONNECT 目标追加路径，确保可见
            pathPref.isVisible = true
            pathPref.title = "Proxy Path"
            pathPref.summaryProvider = EditTextPreference.SimpleSummaryProvider.getInstance()
            // 监听用户输入，写入 profileCacheStore（与标准 PreferenceBinding 同一 Store）
            pathPref.setOnPreferenceChangeListener { _, newValue ->
                DataStore.profileCacheStore.putString("path", newValue as String)
                true
            }
        }

        // —— delHost 追加到 password 所在 category ——
        val screen = preferenceScreen
        for (i in 0 until screen.preferenceCount) {
            val cat = screen.getPreference(i)
            if (cat is PreferenceCategory) {
                if (findPreference<androidx.preference.Preference>("password")?.parent == cat) {
                    if (findPreference<androidx.preference.Preference>("delHost") == null) {
                        SwitchPreference(requireContext()).apply {
                            key = "delHost"
                            title = "Del Host"
                            summary = "CONNECT 请求不发送 Host header"
                            isChecked = DataStore.profileCacheStore.getBoolean("delHost", false)
                            setOnPreferenceChangeListener { _, newValue ->
                                DataStore.profileCacheStore.putBoolean("delHost", newValue as Boolean)
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
        val delHost = DataStore.profileCacheStore.getBoolean("delHost", false)
        val path = DataStore.profileCacheStore.getString("path") ?: ""
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
