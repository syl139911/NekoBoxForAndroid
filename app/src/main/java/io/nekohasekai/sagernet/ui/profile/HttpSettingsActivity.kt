package io.nekohasekai.sagernet.ui.profile

import android.os.Bundle
import android.view.View
import androidx.preference.Preference
import androidx.preference.PreferenceFragmentCompat
import androidx.preference.SwitchPreference
import io.nekohasekai.sagernet.R
import io.nekohasekai.sagernet.fmt.http.HttpBean
import moe.matsuri.nb4a.proxy.PreferenceBinding
import moe.matsuri.nb4a.proxy.Type

class HttpSettingsActivity : StandardV2RaySettingsActivity() {

    override fun createEntity() = HttpBean()

    // 注册 delHost：PreferenceBinding 会自动从 profileCacheStore 读写布尔值，
    // 并在 saveAndExit 时通过父类 serialize()（pbm.fromCacheAll）序列化进数据库。
    private val delHost = pbm.add(PreferenceBinding(Type.Bool, "delHost"))

    override fun PreferenceFragmentCompat.viewCreated(view: View, savedInstanceState: Bundle?) {
        // 找到 serverPort 所在 category，追加 delHost SwitchPreference
        val cat = findPreference<Preference>("serverPort")?.parent as? PreferenceCategory ?: return

        // 动态创建 delHost（仅 HTTP 可见，防止重复创建）
        if (findPreference<Preference>("delHost") == null) {
            SwitchPreference(requireContext()).apply {
                key = "delHost"
                title = getString(R.string.del_host)
                summary = getString(R.string.del_host_sum)
                cat.addPreference(this)
            }
        }
    }
}
