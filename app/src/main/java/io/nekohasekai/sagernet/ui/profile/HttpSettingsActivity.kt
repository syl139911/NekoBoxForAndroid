package io.nekohasekai.sagernet.ui.profile

import android.os.Bundle
import android.view.View
import androidx.preference.EditTextPreference
import androidx.preference.PreferenceCategory
import androidx.preference.PreferenceFragmentCompat
import androidx.preference.SwitchPreference
import io.nekohasekai.sagernet.R
import io.nekohasekai.sagernet.*
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
            pathPref.isVisible = true
            pathPref.title = "Proxy Path"
            pathPref.summaryProvider = EditTextPreference.SimpleSummaryProvider.getInstance()
            // 监听用户输入，直接写回当前编辑的 bean（避免跨 DataStore 实例丢失）
            pathPref.setOnPreferenceChangeListener { _, newValue ->
                val bean = currentHttpBean()
                bean.path = newValue as String
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
                            // 初始值：从当前编辑的 bean 读取
                            isChecked = currentHttpBean().delHost == true
                            setOnPreferenceChangeListener { _, newValue ->
                                val bean = currentHttpBean()
                                bean.delHost = newValue as Boolean
                                // 必须写 profileCacheStore：delHost 不在任何 PreferenceBinding 中，
                                // 而 ProfileManager.createProfile 会先调 applyDefaultValues()（重置为 false）
                                // 再调 init()（写缓存）；若缓存是 false，serialize() 就把 false 写进数据库。
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

    /** 获取当前编辑的 HttpBean（直接引用，修改会落在同一个对象上） */
    private fun currentHttpBean(): HttpBean {
        return if (DataStore.editingId == 0L) {
            // 新建：bean 在 DataStore.profileCacheStore 临时海吨，读偏好即可
            // （PreferenceBinding 在 onCreate 时从 createEntity().init() 的 bean 写了初值）
            createEntity().also { bean ->
                bean.delHost = DataStore.profileCacheStore.getBoolean("delHost", false)
                bean.path = DataStore.profileCacheStore.getString("path") ?: ""
            }
        } else {
            // 编辑：从已加载的 entity 取缓存实例（同一引用，修改直接落 entity.data）
            proxyEntity!!.requireBean() as HttpBean
        }
    }

    override suspend fun saveAndExit() {
        val bean = currentHttpBean()
        val editingId = DataStore.editingId
        if (editingId == 0L) {
            ProfileManager.createProfile(DataStore.editingGroup, bean)
        } else {
            val entity = proxyEntity ?: run { finish(); return }
            if (entity.id == DataStore.selectedProxy) {
                SagerNet.stopService()
            }
            ProfileManager.updateProfile(entity)
        }
        finish()
    }
}
