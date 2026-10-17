// winwait <tag> <timeout-seconds>
// Polls the window-server list every 10 ms and prints "<epoch-seconds> <pid> <onscreen>" as soon as
// a normal (layer 0, >=300x200, alpha>0) window exists whose owning process has <tag> in its
// argv/env (KERN_PROCARGS2). Uses .optionAll, not on-screen-only, because the owner may be in another
// Space/full-screen app and a background-launched window then never counts as "on screen".
// Needs no Screen Recording permission: only owner PID, bounds and alpha are read.
import Foundation
import CoreGraphics

func procArgs(_ pid: pid_t) -> Data? {
    var mib: [Int32] = [CTL_KERN, KERN_PROCARGS2, pid]
    var size = 0
    if sysctl(&mib, 3, nil, &size, nil, 0) != 0 || size == 0 { return nil }
    var buf = [UInt8](repeating: 0, count: size)
    if sysctl(&mib, 3, &buf, &size, nil, 0) != 0 { return nil }
    return Data(buf[0..<size])
}

let args = CommandLine.arguments
guard args.count == 3, let timeout = Double(args[2]) else { print("usage: winwait <tag> <timeout>"); exit(2) }
let tag = args[1].data(using: .utf8)!
var verdict: [pid_t: Bool] = [:]
let deadline = Date().addingTimeInterval(timeout)
while Date() < deadline {
    let list = CGWindowListCopyWindowInfo([.optionAll, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]] ?? []
    for w in list {
        guard (w[kCGWindowLayer as String] as? Int) == 0,
              let pid = w[kCGWindowOwnerPID as String] as? pid_t,
              let b = w[kCGWindowBounds as String] as? [String: Double],
              (b["Width"] ?? 0) >= 300, (b["Height"] ?? 0) >= 200,
              ((w[kCGWindowAlpha as String] as? Double) ?? 0) > 0 else { continue }
        if verdict[pid] == nil { verdict[pid] = procArgs(pid)?.range(of: tag) != nil }
        if verdict[pid] == true {
            let on = (w[kCGWindowIsOnscreen as String] as? Bool) ?? false
            print(String(format: "%.3f %d %d", Date().timeIntervalSince1970, pid, on ? 1 : 0)); exit(0)
        }
    }
    usleep(10_000)
}
print("timeout"); exit(1)
