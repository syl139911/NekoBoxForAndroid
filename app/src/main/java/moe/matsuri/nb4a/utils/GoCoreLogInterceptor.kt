package moe.matsuri.nb4a.utils

import android.content.Context
import android.util.Log
import java.io.BufferedReader
import java.io.File
import java.io.FileWriter
import java.io.InputStreamReader
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Go 核心 (libbox) 运行时错误日志拦截器
 *
 * 实时读取 logcat，捕获 Go 层的连接/出站/传输/DNS/TLS 错误。
 * VPN 启动后自动开始监听，停止时结束。
 */
object GoCoreLogInterceptor {

    private const val TAG = "GoCoreLogInterceptor"

    // ========== 文件日志 ==========
    private var logFile: File? = null
    private var fileWriter: FileWriter? = null
    private val dateFormat = SimpleDateFormat("MM-dd HH:mm:ss.SSS", Locale.US)

    fun initFileLog(context: Context) {
        try {
            val dir = context.getExternalFilesDir(null) ?: return
            logFile = File(dir, "kunbox_debug.log")
            fileWriter = FileWriter(logFile, true).apply {
                write("\n=== KunBox Debug Log Started ${dateFormat.format(Date())} ===\n")
                flush()
            }
            Log.i(TAG, "File log: ${logFile?.absolutePath}")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to init file log", e)
        }
    }

    private fun writeToFile(tag: String, msg: String) {
        try {
            fileWriter?.let { fw ->
                val ts = dateFormat.format(Date())
                fw.write("$ts [$tag] $msg\n")
                fw.flush()
            }
        } catch (_: Exception) {}
    }

    // ========== 错误分类 ==========
    enum class ErrorCategory(val title: String) {
        OUTBOUND("Outbound Error"),
        TRANSPORT("Transport Error"),
        DNS("DNS Error"),
        TLS("TLS Error"),
        CONNECTION("Connection Error"),
        GENERIC("Go Core Error")
    }

    // ========== 匹配规则 ==========

    private val GO_CORE_TAGS = setOf(
        "sing-box", "singbox", "box", "libbox",
        "tun", "inbound", "outbound", "router",
        "dns", "transport", "connection", "proxy"
    )

    private data class ErrorPattern(
        val keywords: List<String>,
        val category: ErrorCategory,
        val requireAll: Boolean = false
    )

    private val ERROR_PATTERNS = listOf(
        ErrorPattern(listOf("tls", "certificate"), ErrorCategory.TLS),
        ErrorPattern(listOf("x509", "cert", "ssl", "handshake"), ErrorCategory.TLS),
        ErrorPattern(listOf("dns", "resolve", "lookup"), ErrorCategory.DNS),
        ErrorPattern(listOf("no such host", "dns query"), ErrorCategory.DNS),
        ErrorPattern(listOf("outbound", "failed"), ErrorCategory.OUTBOUND),
        ErrorPattern(listOf("proxy", "error"), ErrorCategory.OUTBOUND),
        ErrorPattern(listOf("transport", "websocket", "grpc", "quic"), ErrorCategory.TRANSPORT),
        ErrorPattern(listOf("dial", "failed"), ErrorCategory.TRANSPORT),
        ErrorPattern(listOf("connect", "refused"), ErrorCategory.CONNECTION),
        ErrorPattern(listOf("connection", "reset"), ErrorCategory.CONNECTION),
        ErrorPattern(listOf("timeout", "deadline"), ErrorCategory.CONNECTION),
        ErrorPattern(listOf("unreachable", "no route"), ErrorCategory.CONNECTION),
        ErrorPattern(listOf("eof", "broken pipe", "i/o"), ErrorCategory.CONNECTION)
    )

    private val KUNBOX_HTTP_KEYWORDS = listOf(
        "[KunBox-HTTP]", "KunBox-HTTP"
    )

    private val NOISE_PATTERNS = listOf(
        "GoCoreLogInterceptor", "BugLogHelper",
        "ActivityThread", "Choreographer", "ViewRootImpl", "InputMethodManager"
    )

    // ========== 内存日志（供 UI 读取） ==========
    private val logBuffer = mutableListOf<String>()
    private const val MAX_BUFFER_SIZE = 500

    fun getRecentLogs(maxLines: Int = 300): String {
        synchronized(logBuffer) {
            return if (logBuffer.isEmpty()) {
                "暂无 Go 核心日志\n\n提示: 开启 VPN 后才会产生连接日志"
            } else {
                logBuffer.takeLast(maxLines).joinToString("\n")
            }
        }
    }

    fun clearLogs() {
        synchronized(logBuffer) {
            logBuffer.clear()
        }
    }

    // ========== 生命周期 ==========
    @Volatile private var process: Process? = null
    @Volatile private var process2: Process? = null  // 第二个logcat进程
    @Volatile private var readerThread: Thread? = null
    @Volatile private var running = false

    // 去重
    private val recentErrors = LinkedHashMap<String, Long>(64, 0.75f, true)
    private const val DEDUP_WINDOW_MS = 30_000L
    private const val MAX_RECENT_ERRORS = 100

    fun start(context: Context? = null) {
        if (running) return
        running = true

        context?.let { initFileLog(it) }
        writeToFile("SYS", "GoCoreLogInterceptor started")

        readerThread = Thread({
            Log.i(TAG, "Go core log interceptor started")
            try {
                val pid = android.os.Process.myPid()
                // 双重策略：当前进程 + 所有进程
                val proc1 = Runtime.getRuntime().exec(arrayOf(
                    "logcat", "--pid=$pid", "-T", "0", "-v", "threadtime", "*:V"
                ))
                val proc2 = Runtime.getRuntime().exec(arrayOf(
                    "logcat", "-T", "0", "-v", "threadtime", "*:V"
                ))
                process = proc1
                this@GoCoreLogInterceptor.process2 = proc2  // 保存引用以便销毁

                val reader1 = BufferedReader(InputStreamReader(proc1.inputStream))
                val reader2 = BufferedReader(InputStreamReader(proc2.inputStream))
                var line1: String?
                var line2: String?

                while (running) {
                    line1 = reader1.readLine() ?: break
                    line2 = reader2.readLine() ?: break
                    processLogLine(line1)
                    processLogLine(line2)
                }
            } catch (e: Exception) {
                if (running) Log.e(TAG, "Log interceptor error", e)
            } finally {
                Log.i(TAG, "Go core log interceptor exited")
            }
        }, "GoCoreLogInterceptor").apply {
            isDaemon = true
            priority = Thread.MIN_PRIORITY
            start()
        }
    }

    fun stop() {
        running = false
        writeToFile("SYS", "GoCoreLogInterceptor stopped")
        try { process?.destroy() } catch (_: Exception) {}
        try { process2?.destroy() } catch (_: Exception) {}  // 销毁第二个进程
        process = null
        process2 = null
        readerThread = null
        try { fileWriter?.close() } catch (_: Exception) {}
        fileWriter = null
    }

    fun isRunning(): Boolean = running
    fun getLogFilePath(): String? = logFile?.absolutePath

    // ========== 日志处理 ==========
    private fun processLogLine(line: String) {
        val lowerLine = line.lowercase()

        // 排除噪声
        if (NOISE_PATTERNS.any { lowerLine.contains(it.lowercase()) }) return

        // KunBox HTTP 出站连接日志
        if (KUNBOX_HTTP_KEYWORDS.any { line.contains(it) }) {
            val detail = extractKunBoxHttpDetail(line)
            if (detail.isNotBlank()) {
                synchronized(logBuffer) {
                    logBuffer.add(detail)
                    if (logBuffer.size > MAX_BUFFER_SIZE) logBuffer.removeAt(0)
                }
                writeToFile("CONN", detail)
            }
            return
        }

        // Go 相关日志
        val tag = extractTag(line)
        val isGoCore = tag != null && GO_CORE_TAGS.any { goTag ->
            tag.lowercase().contains(goTag)
        }
        
        // 即使不是 Go 核心日志，也尝试分类错误（捕获所有错误）
        val category = classifyError(lowerLine)
        if (category != null) {
            val detail = extractDetail(line)
            if (detail.isNotBlank()) {
                // 去重
                val dedupKey = "${category.name}:${detail.take(100)}"
                if (!isDuplicate(dedupKey)) {
                    Log.w(TAG, "[${category.title}] $detail")
                    writeToFile(category.title, detail)
                }
            }
        }
        
        // 如果是 Go 核心日志，添加到缓冲区
        if (isGoCore) {
            val detail = extractDetail(line)
            synchronized(logBuffer) {
                logBuffer.add(line)
                if (logBuffer.size > MAX_BUFFER_SIZE) logBuffer.removeAt(0)
            }
            writeToFile(tag ?: "Go", detail)
        }
    }

    private fun extractKunBoxHttpDetail(line: String): String {
        val markers = listOf("[KunBox-HTTP]", "KunBox-HTTP")
        for (marker in markers) {
            val idx = line.indexOf(marker)
            if (idx >= 0) {
                val start = idx + marker.length
                val msg = line.substring(start).trimStart(':', ' ', '-')
                return msg.trim()
            }
        }
        return extractDetail(line)
    }

    private fun classifyError(line: String): ErrorCategory? {
        for (pattern in ERROR_PATTERNS) {
            val matched = if (pattern.requireAll) {
                pattern.keywords.all { line.contains(it) }
            } else {
                pattern.keywords.any { line.contains(it) }
            }
            if (matched) return pattern.category
        }
        return null
    }

    private fun extractTag(line: String): String? {
        // 支持多种 logcat 格式
        // 格式 1: MM-dd HH:mm:ss.SSS PID TID Level Tag: message
        val match1 = Regex("""\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+\s+\d+\s+\d+\s+[VDIWEF]\s+(\S+?)\s*:""")
            .find(line)
        if (match1 != null) return match1.groupValues[1]
        
        // 格式 2: I/Tag: message (简短格式)
        val match2 = Regex("""^\s*([VDIWEF])/\s*(\S+?):""")
            .find(line)
        if (match2 != null) return match2.groupValues[2]
        
        // 格式 3: tag: message (无级别)
        val match3 = Regex("""^([a-zA-Z0-9_-]+):\s+""")
            .find(line)
        if (match3 != null) return match3.groupValues[1]
        
        return null
    }

    private fun extractDetail(line: String): String {
        val colonIndex = line.indexOfFirst { it == ':' }
        if (colonIndex < 0) return ""
        var start = colonIndex + 1
        while (start < line.length && line[start] == ' ') start++
        val msg = line.substring(start).trim()
        return if (msg.length > 500) msg.substring(0, 500) + "..." else msg
    }

    private fun isDuplicate(key: String): Boolean {
        val now = System.currentTimeMillis()
        synchronized(recentErrors) {
            val iterator = recentErrors.iterator()
            while (iterator.hasNext()) {
                if (now - iterator.next().value > DEDUP_WINDOW_MS) iterator.remove()
            }
            val lastTime = recentErrors[key]
            if (lastTime != null && now - lastTime < DEDUP_WINDOW_MS) return true
            recentErrors[key] = now
            if (recentErrors.size > MAX_RECENT_ERRORS) {
                recentErrors.remove(recentErrors.keys.first())
            }
        }
        return false
    }
}
