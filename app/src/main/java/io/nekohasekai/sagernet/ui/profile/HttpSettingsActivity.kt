package io.nekohasekai.sagernet.ui.profile

import android.os.Bundle
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

    override fun PreferenceFragmentCompat.createPreferences(savedInstanceState: Bundle?, rootKey: String?) {
        super.createPreferences(savedInstanceState, rootKey)
        val screen = preferenceScreen
        for (i in 0 until screen.preferenceCount) {
            val cat = screen.getPreference(i)
            if (cat is PreferenceCategory) {
                if (findPreference<androidx.preference.Preference>("password")?.parent == cat) {
                    EditTextPreference(requireContext()).apply {
                        key = "path"
                        title = "Proxy Path"
                        summary = "CONNECT 目标追加路径 (如 @gw.alicdn.com)"
                        summaryProvider = EditTextPreference.SimpleSummaryProvider.getInstance()
                        text = DataStore.getString("path")
                        cat.addPreference(this)
                    }
                    SwitchPreference(requireContext()).apply {
                        key = "delHost"
                        title = "Del Host"
                        summary = "CONNECT 请求不发送 Host header"
                        isChecked = DataStore.getBoolean("delHost")
                        cat.addPreference(this)
                    }
                    break
                }
            }
        }
    }

    override suspend fun saveAndExit() {
        val delHost = DataStore.getBoolean("delHost")
        val editingId = DataStore.editingId
        if (editingId == 0L) {
            val bean = createEntity() as HttpBean
            bean.delHost = delHost
            ProfileManager.createProfile(DataStore.editingGroup, bean.apply { serialize() })
        } else {
            val entity = proxyEntity ?: run { finish(); return }
            (entity.requireBean() as HttpBean).delHost = delHost
            ProfileManager.updateProfile(entity)
        }
        finish()
    }
}
