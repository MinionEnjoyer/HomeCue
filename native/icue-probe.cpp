#include <windows.h>

#include <atomic>
#include <chrono>
#include <iostream>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

constexpr int kStringSize = 128;
constexpr int kDeviceMax = 64;
constexpr int kLedMax = 512;
constexpr unsigned int kAllDevices = 0xFFFFFFFFu;
constexpr unsigned int kSuccess = 0;
constexpr unsigned int kConnected = 6;

struct CorsairVersion { int major; int minor; int patch; };
struct CorsairSessionDetails {
    CorsairVersion clientVersion;
    CorsairVersion serverVersion;
    CorsairVersion serverHostVersion;
};
struct CorsairSessionStateChanged {
    unsigned int state;
    CorsairSessionDetails details;
};
struct CorsairDeviceFilter { unsigned int deviceTypeMask; };
struct CorsairDeviceInfo {
    unsigned int type;
    char id[kStringSize];
    char serial[kStringSize];
    char model[kStringSize];
    int ledCount;
    int channelCount;
};
struct CorsairLedPosition { unsigned int id; double cx; double cy; };

using SessionHandler = void (*)(void *, const CorsairSessionStateChanged *);
using ConnectFn = unsigned int (*)(SessionHandler, void *);
using DisconnectFn = unsigned int (*)();
using GetDevicesFn = unsigned int (*)(const CorsairDeviceFilter *, int, CorsairDeviceInfo *, int *);
using GetLedPositionsFn = unsigned int (*)(const char *, int, CorsairLedPosition *, int *);

std::string escape_json(const char *raw) {
    std::ostringstream out;
    for (const unsigned char ch : std::string(raw ? raw : "")) {
        switch (ch) {
            case '\\': out << "\\\\"; break;
            case '"': out << "\\\""; break;
            case '\n': out << "\\n"; break;
            case '\r': out << "\\r"; break;
            case '\t': out << "\\t"; break;
            default:
                if (ch >= 0x20) out << ch;
        }
    }
    return out.str();
}

int wmain(int argc, wchar_t **argv) {
    const wchar_t *library_path = argc > 1 ? argv[1] : L"iCUESDK.x64_2019.dll";
    HMODULE library = LoadLibraryW(library_path);
    if (!library) {
        std::cout << "{\"connected\":false,\"error\":\"dll-not-found\",\"devices\":[]}";
        return 2;
    }

    const auto connect = reinterpret_cast<ConnectFn>(GetProcAddress(library, "CorsairConnect"));
    const auto disconnect = reinterpret_cast<DisconnectFn>(GetProcAddress(library, "CorsairDisconnect"));
    const auto get_devices = reinterpret_cast<GetDevicesFn>(GetProcAddress(library, "CorsairGetDevices"));
    const auto get_leds = reinterpret_cast<GetLedPositionsFn>(GetProcAddress(library, "CorsairGetLedPositions"));
    if (!connect || !disconnect || !get_devices || !get_leds) {
        std::cout << "{\"connected\":false,\"error\":\"missing-export\",\"devices\":[]}";
        FreeLibrary(library);
        return 3;
    }

    std::atomic<unsigned int> state{0};
    const auto handler = [](void *context, const CorsairSessionStateChanged *event) {
        if (context && event) static_cast<std::atomic<unsigned int> *>(context)->store(event->state);
    };
    const unsigned int connect_error = connect(handler, &state);
    if (connect_error != kSuccess) {
        std::cout << "{\"connected\":false,\"connectError\":" << connect_error << ",\"devices\":[]}";
        FreeLibrary(library);
        return 4;
    }

    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(10);
    while (state.load() != kConnected && std::chrono::steady_clock::now() < deadline)
        std::this_thread::sleep_for(std::chrono::milliseconds(25));

    if (state.load() != kConnected) {
        std::cout << "{\"connected\":false,\"sessionState\":" << state.load() << ",\"devices\":[]}";
        disconnect();
        FreeLibrary(library);
        return 5;
    }

    CorsairDeviceFilter filter{kAllDevices};
    CorsairDeviceInfo devices[kDeviceMax]{};
    int device_count = 0;
    const unsigned int enumeration_error = get_devices(&filter, kDeviceMax, devices, &device_count);

    std::ostringstream json;
    json << "{\"connected\":true,\"enumerationError\":" << enumeration_error << ",\"devices\":[";
    if (enumeration_error == kSuccess) {
        for (int index = 0; index < device_count; ++index) {
            if (index) json << ',';
            CorsairLedPosition leds[kLedMax]{};
            int led_count = 0;
            const unsigned int led_error = get_leds(devices[index].id, kLedMax, leds, &led_count);
            json << "{\"id\":\"" << escape_json(devices[index].id)
                 << "\",\"model\":\"" << escape_json(devices[index].model)
                 << "\",\"type\":" << devices[index].type
                 << ",\"channelCount\":" << devices[index].channelCount
                 << ",\"ledError\":" << led_error << ",\"ledIds\":[";
            if (led_error == kSuccess) {
                for (int led_index = 0; led_index < led_count; ++led_index) {
                    if (led_index) json << ',';
                    json << leds[led_index].id;
                }
            }
            json << "]}";
        }
    }
    json << "]}";
    std::cout << json.str();

    disconnect();
    FreeLibrary(library);
    return enumeration_error == kSuccess ? 0 : 6;
}
