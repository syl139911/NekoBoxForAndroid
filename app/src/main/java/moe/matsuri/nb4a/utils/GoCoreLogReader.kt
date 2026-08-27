package moe.matsuri.nb4a.utils

import android.util.Log
import java.io.BufferedReader
import java.io.InputStreamReader

/**
 * 读取 Go 核心 (sing-box) 的 logcat 日志
 * 捕获 HTTP CONNECT 相关输出，帮助排查代理连接问题
 */
object GoCoreLogReader {

    private const val TAG = "GoCoreLogReader"

    // Go 核心日志关键词
    private val GO_CORE_KEYWORDS = listOf(
        "HTTP CONNECT",
        "sing-box",
        "outbound",
        "transport",
        "dns",
        "resolve",
        "lookup",
        "nameserver",
        "no such host",
        "failed",
        "error",
        "timeout",
        "refused",
        "tls",
        "certificate",
        "dial",
        "connect"
    )

    /**
     * 读取最近的 Go 核心日志
     * @param maxLines 最多返回行数
     * @return 日志文本
     */
    fun readRecentLogs(maxLines: Int = 200): String {
        return try {
            val pid = android.os.Process.myPid()
            val proc = Runtime.getRuntime().exec(
                arrayOf("logcat", "-d", "--pid=$pid", "-t", maxLines.toString())
            )

            val reader = BufferedReader(InputStreamReader(proc.inputStream))
            val sb = StringBuilder()
            var line: String?

            while (reader.readLine().also { line = it } != null) {
                val l = line ?: continue
                val lower = l.lowercase()

                // 只保留 Go 核心相关日志
                if (GO_CORE_KEYWORDS.any { lower.contains(it.lowercase()) }) {
                    sb.appendLine(l)
                }
            }

            proc.waitFor()

            if (sb.isEmpty()) {
                "暂无 Go 核心日志\n\n提示: 开启 VPN 后才会产生连接日志"
            } else {
                sb.toString()
            }
        } catch (e: Exception) {
            "读取日志失败: ${e.message}"
        }
    }

    /**
     * 读取所有最近日志（不限关键词）
     * @param maxLines 最多返回行数
     * @return 日志文本
     */
    fun readAllRecentLogs(maxLines: Int = 500): String {
        return try {
            val pid = android.os.Process.myPid()
            val proc = Runtime.getRuntime().exec(
                arrayOf("logcat", "-d", "--pid=$pid", "-t", maxLines.toString())
            )

            val reader = BufferedReader(InputStreamReader(proc.inputStream))
            val sb = StringBuilder()
            var line: String?

            while (reader.readLine().also { line = it } != null) {
                sb.appendLine(line)
            }

            proc.waitFor()

            if (sb.isEmpty()) {
                "暂无日志"
            } else {
                sb.toString()
            }
        } catch (e: Exception) {
            "读取日志失败: ${e.message}"
        }
    }
}
