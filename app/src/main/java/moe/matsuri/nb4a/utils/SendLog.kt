package moe.matsuri.nb4a.utils

import android.content.Context
import android.content.Intent
import androidx.core.content.FileProvider
import io.nekohasekai.sagernet.BuildConfig
import io.nekohasekai.sagernet.R
import io.nekohasekai.sagernet.SagerNet
import io.nekohasekai.sagernet.ktx.Logs
import io.nekohasekai.sagernet.ktx.app
import io.nekohasekai.sagernet.ktx.use
import io.nekohasekai.sagernet.utils.CrashHandler
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.io.IOException

object SendLog {
    // Create full log and send
    fun sendLog(context: Context, title: String) {
        val logFile = File.createTempFile(
            "$title ",
            ".log",
            File(app.cacheDir, "log").also { it.mkdirs() })

        val sb = StringBuilder()

        // Header
        sb.append(CrashHandler.buildReportHeader())
        sb.appendLine("\n")

        // GoCoreLogInterceptor 缓冲区（过滤后的关键日志）
        sb.appendLine("=== Go Core Logs (Filtered) ===")
        sb.appendLine(GoCoreLogInterceptor.getRecentLogs(500))
        sb.appendLine()

        // kunbox_debug.log 文件（如果存在）
        val debugLog = GoCoreLogInterceptor.getLogFilePath()?.let { File(it) }
        if (debugLog != null && debugLog.exists() && debugLog.length() > 0) {
            sb.appendLine("=== KunBox Debug Log ===")
            try {
                val len = debugLog.length()
                val stream = FileInputStream(debugLog)
                // 最多读 200KB
                if (len > 200 * 1024) stream.skip(len - 200 * 1024)
                sb.append(String(stream.use { it.readBytes() }))
            } catch (e: Exception) {
                sb.appendLine("Read error: ${e.message}")
            }
            sb.appendLine()
        }

        // 全量 logcat（放在最后，可能很大）
        sb.appendLine("=== Full Logcat ===")
        logFile.writeText(sb.toString())

        try {
            Runtime.getRuntime().exec(arrayOf("logcat", "-d")).inputStream.use(
                FileOutputStream(logFile, true)
            )
            logFile.appendText("\n")
        } catch (e: IOException) {
            Logs.w(e)
            logFile.appendText("Export logcat error: " + CrashHandler.formatThrowable(e))
        }

        // neko.log
        logFile.appendText("\n=== NekoLog ===\n")
        logFile.appendBytes(getNekoLog(0))

        context.startActivity(
            Intent.createChooser(
                Intent(Intent.ACTION_SEND).setType("text/x-log")
                    .setFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                    .putExtra(
                        Intent.EXTRA_STREAM, FileProvider.getUriForFile(
                            context, BuildConfig.APPLICATION_ID + ".cache", logFile
                        )
                    ), context.getString(R.string.abc_shareactionprovider_share_with)
            )
        )
    }

    // Get log bytes from neko.log
    fun getNekoLog(max: Long): ByteArray {
        return try {
            val file = File(
                SagerNet.application.cacheDir,
                "neko.log"
            )
            val len = file.length()
            val stream = FileInputStream(file)
            if (max in 1 until len) {
                stream.skip(len - max) // TODO string?
            }
            stream.use { it.readBytes() }
        } catch (e: Exception) {
            e.stackTraceToString().toByteArray()
        }
    }
}
