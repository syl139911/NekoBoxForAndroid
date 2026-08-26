package io.nekohasekai.sagernet.ui.profile

import android.os.Bundle
import android.view.View
import androidx.preference.Preference
import androidx.preference.PreferenceFragmentCompat
import io.nekohasekai.sagernet.fmt.http.HttpBean
import moe.matsuri.nb4a.proxy.PreferenceBinding
import moe.matsuri.nb4a.proxy.Type

class HttpSettingsActivity : StandardV2RaySettingsActivity() {

    override fun createEntity() = HttpBean()

    private val delHost = pbm.add(PreferenceBinding(Type.Bool, "delHost"))

    override fun PreferenceFragmentCompat.viewCreated(view: View, savedInstanceState: Bundle?) {
        // delHost 已在 XML 中，无需动态创建
        // path 排序已由 pathHttp 处理，无需 order 重排
        findPreference<Preference>("host")?.isVisible = false
        findPreference<Preference>("path")?.title = "path"
    }
}
