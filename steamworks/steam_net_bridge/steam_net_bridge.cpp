/**
 * steam_net_bridge.cpp — Pybind11 C++ köprü modülü
 *
 * Steam ISteamMatchmaking + ISteamNetworkingMessages API'lerini
 * Python'a güvenli polling mimarisiyle sunar.
 *
 * Derleme için Steamworks SDK gereklidir:
 *   steamworks/sdk/public/steam/ (header'lar)
 *   steamworks/sdk/redistributable_bin/win64/steam_api64.lib (link)
 *
 * Mimarisi:
 *   - C++ tarafı tüm asenkron callback'leri kendi içinde yakalar.
 *   - Gelen ağ paketleri ve olaylar std::deque kuyruğuna eklenir.
 *   - Python tarafı her frame (60 FPS) sadece poll_events() ve poll_messages()
 *     çağırarak kuyruktan okur. Böylece GIL çakışması veya segfault olmaz.
 */

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <steam/steam_api.h>
#include <steam/isteammatchmaking.h>
#include <steam/isteamnetworkingmessages.h>
#include <steam/isteamfriends.h>

#include <string>
#include <array>
#include <vector>
#include <deque>
#include <tuple>
#include <algorithm>
#include <unordered_map>
#include <mutex>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>

namespace py = pybind11;

namespace
{
    uint32_t md5_left_rotate(uint32_t value, uint32_t shift)
    {
        return (value << shift) | (value >> (32 - shift));
    }

    std::array<uint8_t, 16> md5_digest(const std::string &input)
    {
        static constexpr uint32_t kShifts[64] = {
            7,
            12,
            17,
            22,
            7,
            12,
            17,
            22,
            7,
            12,
            17,
            22,
            7,
            12,
            17,
            22,
            5,
            9,
            14,
            20,
            5,
            9,
            14,
            20,
            5,
            9,
            14,
            20,
            5,
            9,
            14,
            20,
            4,
            11,
            16,
            23,
            4,
            11,
            16,
            23,
            4,
            11,
            16,
            23,
            4,
            11,
            16,
            23,
            6,
            10,
            15,
            21,
            6,
            10,
            15,
            21,
            6,
            10,
            15,
            21,
            6,
            10,
            15,
            21,
        };

        std::array<uint32_t, 64> table{};
        for (size_t index = 0; index < table.size(); ++index)
        {
            table[index] = static_cast<uint32_t>(
                std::floor(std::abs(std::sin(static_cast<double>(index + 1))) * 4294967296.0));
        }

        std::vector<uint8_t> message(input.begin(), input.end());
        const uint64_t bitLength = static_cast<uint64_t>(message.size()) * 8ull;
        message.push_back(0x80);
        while ((message.size() % 64) != 56)
        {
            message.push_back(0x00);
        }
        for (int shift = 0; shift < 8; ++shift)
        {
            message.push_back(static_cast<uint8_t>((bitLength >> (shift * 8)) & 0xffu));
        }

        uint32_t a0 = 0x67452301u;
        uint32_t b0 = 0xefcdab89u;
        uint32_t c0 = 0x98badcfeu;
        uint32_t d0 = 0x10325476u;

        for (size_t offset = 0; offset < message.size(); offset += 64)
        {
            uint32_t words[16] = {};
            for (int wordIndex = 0; wordIndex < 16; ++wordIndex)
            {
                const size_t wordOffset = offset + static_cast<size_t>(wordIndex) * 4;
                words[wordIndex] =
                    static_cast<uint32_t>(message[wordOffset]) |
                    (static_cast<uint32_t>(message[wordOffset + 1]) << 8) |
                    (static_cast<uint32_t>(message[wordOffset + 2]) << 16) |
                    (static_cast<uint32_t>(message[wordOffset + 3]) << 24);
            }

            uint32_t a = a0;
            uint32_t b = b0;
            uint32_t c = c0;
            uint32_t d = d0;

            for (uint32_t index = 0; index < 64; ++index)
            {
                uint32_t f = 0;
                uint32_t g = 0;

                if (index < 16)
                {
                    f = (b & c) | ((~b) & d);
                    g = index;
                }
                else if (index < 32)
                {
                    f = (d & b) | ((~d) & c);
                    g = (5 * index + 1) % 16;
                }
                else if (index < 48)
                {
                    f = b ^ c ^ d;
                    g = (3 * index + 5) % 16;
                }
                else
                {
                    f = c ^ (b | (~d));
                    g = (7 * index) % 16;
                }

                const uint32_t rotated = a + f + table[index] + words[g];
                const uint32_t previousD = d;
                d = c;
                c = b;
                b = b + md5_left_rotate(rotated, kShifts[index]);
                a = previousD;
            }

            a0 += a;
            b0 += b;
            c0 += c;
            d0 += d;
        }

        std::array<uint8_t, 16> digest{};
        const uint32_t state[4] = {a0, b0, c0, d0};
        for (size_t stateIndex = 0; stateIndex < 4; ++stateIndex)
        {
            const uint32_t value = state[stateIndex];
            const size_t digestOffset = stateIndex * 4;
            digest[digestOffset] = static_cast<uint8_t>(value & 0xffu);
            digest[digestOffset + 1] = static_cast<uint8_t>((value >> 8) & 0xffu);
            digest[digestOffset + 2] = static_cast<uint8_t>((value >> 16) & 0xffu);
            digest[digestOffset + 3] = static_cast<uint8_t>((value >> 24) & 0xffu);
        }
        return digest;
    }

    std::string generate_lobby_code(uint64_t lobbyId)
    {
        if (!lobbyId)
        {
            return "000000";
        }

        const auto digest = md5_digest(std::to_string(lobbyId));
        const uint32_t prefix =
            (static_cast<uint32_t>(digest[0]) << 24) |
            (static_cast<uint32_t>(digest[1]) << 16) |
            (static_cast<uint32_t>(digest[2]) << 8) |
            static_cast<uint32_t>(digest[3]);
        char buffer[7] = {};
        std::snprintf(buffer, sizeof(buffer), "%06u", prefix % 1000000u);
        return std::string(buffer);
    }
} // namespace

// ---------- Event / Message yapıları ----------

struct NetEvent
{
    std::string type;  // "lobby_created", "lobby_joined", "lobby_member_joined", ...
    uint64_t steam_id; // İlgili Steam ID (veya lobby id)
    std::string data;  // Ek veri (isim, hata mesajı vs.)
};

struct NetMessage
{
    uint64_t sender;     // Gönderen Steam ID
    std::string payload; // JSON veya binary veri
    int channel;         // Kanal numarası
};

// ---------- Ana köprü sınıfı ----------

class SteamNetBridge
{
public:
    SteamNetBridge()
        : m_matchmaking(nullptr), m_messages(nullptr), m_friends(nullptr), m_currentLobby(k_steamIDNil), m_lobbyReady(false), m_joinRequestedTime(0), m_lobbyListRequestActive(false), m_pendingLobbyVisibility("private"), m_pendingLobbyRequiresCode(true), m_isShutdown(false)
    {
    }

    ~SteamNetBridge()
    {
        // Destructor'da Steam API çağrısı YAPMA!
        // SteamAPI_Shutdown() çağrıldıktan sonra interface pointer'ları geçersiz
        // olur ve macOS'ta donmaya neden olur. Temizlik için shutdown() kullanın.
    }

    // ============ Başlatma ============

    bool init()
    {
        if (m_isShutdown)
            return false;
        m_matchmaking = SteamMatchmaking();
        m_messages = SteamNetworkingMessages();
        m_friends = SteamFriends();

        if (!m_matchmaking || !m_messages || !m_friends)
        {
            push_event("error", 0, "Steam interface'leri alinamadi. SteamAPI_Init() cagrildi mi?");
            return false;
        }

        push_event("init_ok", SteamUser()->GetSteamID().IsValid() ? SteamUser()->GetSteamID().ConvertToUint64() : 0, "");
        return true;
    }

    // ============ Temiz Kapanma ============

    void shutdown()
    {
        // SteamAPI_Shutdown() ÖNCESINDE çağrılmalı.
        // Aktıf lobiyi terket ve interface pointer'larını sıfırla.
        if (m_isShutdown)
            return;
        m_isShutdown = true;

        if (m_matchmaking && m_currentLobby.IsValid() && m_currentLobby != k_steamIDNil)
        {
            m_matchmaking->LeaveLobby(m_currentLobby);
            m_currentLobby = k_steamIDNil;
            m_lobbyReady = false;
        }

        m_matchmaking = nullptr;
        m_messages = nullptr;
        m_friends = nullptr;
    }

    // ============ Lobi İşlemleri ============

    void create_lobby(int max_members = 2)
    {
        if (!m_matchmaking || m_isShutdown)
            return;
        // Quadrix'te "ozel" lobi kod ile bulunabilir olmalidir.
        // Steam dokumanina gore RequestLobbyList sadece Public ve Invisible
        // lobileri dondurur; Private/FriendsOnly lobileri listelemez.
        // Bu nedenle oyun-ici private/public semantigini metadata ile,
        // Steam-search discoverability'yi ise Invisible lobby type ile ayiriyoruz.
        set_pending_lobby_metadata(k_ELobbyTypeInvisible);
        SteamAPICall_t call = m_matchmaking->CreateLobby(k_ELobbyTypeInvisible, max_members);
        m_lobbyCreatedResult.Set(call, this, &SteamNetBridge::OnLobbyCreated);
    }

    void create_public_lobby(int max_members = 2)
    {
        if (!m_matchmaking || m_isShutdown)
            return;
        set_pending_lobby_metadata(k_ELobbyTypePublic);
        SteamAPICall_t call = m_matchmaking->CreateLobby(k_ELobbyTypePublic, max_members);
        m_lobbyCreatedResult.Set(call, this, &SteamNetBridge::OnLobbyCreated);
    }

    void join_lobby(uint64_t lobby_id)
    {
        if (!m_matchmaking)
            return;
        CSteamID lid(lobby_id);
        SteamAPICall_t call = m_matchmaking->JoinLobby(lid);
        m_lobbyEnterResult.Set(call, this, &SteamNetBridge::OnLobbyEnter);
    }

    void leave_lobby()
    {
        if (!m_matchmaking || m_isShutdown)
            return;
        if (m_currentLobby.IsValid() && m_currentLobby != k_steamIDNil)
        {
            m_matchmaking->LeaveLobby(m_currentLobby);
            push_event("lobby_left", m_currentLobby.ConvertToUint64(), "");
            m_currentLobby = k_steamIDNil;
            m_lobbyReady = false;
        }
    }

    void set_lobby_data(const std::string &key, const std::string &value)
    {
        if (!m_matchmaking || m_isShutdown || !m_currentLobby.IsValid())
            return;
        m_matchmaking->SetLobbyData(m_currentLobby, key.c_str(), value.c_str());
    }

    std::string get_lobby_data(const std::string &key)
    {
        if (!m_matchmaking || m_isShutdown || !m_currentLobby.IsValid())
            return "";
        const char *val = m_matchmaking->GetLobbyData(m_currentLobby, key.c_str());
        return val ? std::string(val) : "";
    }

    std::string get_lobby_data_for(uint64_t lobby_id, const std::string &key)
    {
        if (!m_matchmaking || m_isShutdown)
            return "";
        CSteamID lid(lobby_id);
        if (!lid.IsValid())
            return "";
        const char *val = m_matchmaking->GetLobbyData(lid, key.c_str());
        return val ? std::string(val) : "";
    }

    bool request_lobby_data(uint64_t lobby_id)
    {
        if (!m_matchmaking || m_isShutdown)
            return false;
        CSteamID lid(lobby_id);
        if (!lid.IsValid())
            return false;
        return m_matchmaking->RequestLobbyData(lid);
    }

    std::vector<uint64_t> get_lobby_members()
    {
        std::vector<uint64_t> members;
        if (!m_matchmaking || m_isShutdown || !m_currentLobby.IsValid())
            return members;
        int count = m_matchmaking->GetNumLobbyMembers(m_currentLobby);
        for (int i = 0; i < count; i++)
        {
            CSteamID member = m_matchmaking->GetLobbyMemberByIndex(m_currentLobby, i);
            members.push_back(member.ConvertToUint64());
        }
        return members;
    }

    uint64_t get_lobby_owner()
    {
        if (!m_matchmaking || m_isShutdown || !m_currentLobby.IsValid())
            return 0;
        return m_matchmaking->GetLobbyOwner(m_currentLobby).ConvertToUint64();
    }

    uint64_t get_current_lobby_id()
    {
        if (!m_currentLobby.IsValid())
            return 0;
        return m_currentLobby.ConvertToUint64();
    }

    bool is_in_lobby()
    {
        return m_currentLobby.IsValid() && m_currentLobby != k_steamIDNil;
    }

    void invite_friend()
    {
        if (!m_friends || m_isShutdown || !m_currentLobby.IsValid())
            return;
        m_friends->ActivateGameOverlayInviteDialog(m_currentLobby);
    }

    // ============ Lobi Tipi Yönetimi ============

    void create_lobby_with_type(int lobby_type, int max_members = 2)
    {
        if (!m_matchmaking || m_isShutdown)
            return;
        ELobbyType type = static_cast<ELobbyType>(lobby_type);
        set_pending_lobby_metadata(type);
        SteamAPICall_t call = m_matchmaking->CreateLobby(type, max_members);
        m_lobbyCreatedResult.Set(call, this, &SteamNetBridge::OnLobbyCreated);
    }

    bool set_lobby_type(int lobby_type)
    {
        if (!m_matchmaking || m_isShutdown || !m_currentLobby.IsValid())
            return false;
        return m_matchmaking->SetLobbyType(m_currentLobby,
                                           static_cast<ELobbyType>(lobby_type));
    }

    bool set_lobby_joinable(bool joinable)
    {
        if (!m_matchmaking || m_isShutdown || !m_currentLobby.IsValid())
            return false;
        return m_matchmaking->SetLobbyJoinable(m_currentLobby, joinable);
    }

    // ============ Lobi Listesi (Public Matchmaking) ============

    void add_request_lobby_list_string_filter(const std::string &key,
                                              const std::string &value)
    {
        if (!m_matchmaking || m_isShutdown)
            return;
        m_matchmaking->AddRequestLobbyListStringFilter(
            key.c_str(), value.c_str(), k_ELobbyComparisonEqual);
    }

    void add_request_lobby_list_distance_filter(int distance_filter)
    {
        if (!m_matchmaking || m_isShutdown)
            return;
        m_matchmaking->AddRequestLobbyListDistanceFilter(
            static_cast<ELobbyDistanceFilter>(distance_filter));
    }

    void request_lobby_list()
    {
        if (!m_matchmaking || m_isShutdown)
            return;
        // Quadrix lobilerini filtrele
        m_matchmaking->AddRequestLobbyListStringFilter("game", "quadrix",
                                                       k_ELobbyComparisonEqual);
        SteamAPICall_t call = m_matchmaking->RequestLobbyList();
        m_lobbyListResult.Set(call, this, &SteamNetBridge::OnLobbyListReceived);
    }

    // ============ Ağ Mesajları ============

    bool send_message(uint64_t target_steam_id, const std::string &data, bool reliable, int channel = 0)
    {
        if (!m_messages || m_isShutdown)
            return false;

        SteamNetworkingIdentity identity;
        identity.SetSteamID64(target_steam_id);

        int flags = reliable
                        ? k_nSteamNetworkingSend_ReliableNoNagle
                        : k_nSteamNetworkingSend_UnreliableNoDelay;

        EResult res = m_messages->SendMessageToUser(
            identity,
            data.c_str(),
            (uint32)data.size(),
            flags,
            channel);

        return res == k_EResultOK;
    }

    bool send_message_to_lobby(const std::string &data, bool reliable, int channel = 0)
    {
        // Lobi'deki tüm üyelere gönder (kendimiz hariç)
        if (!m_matchmaking || m_isShutdown || !m_currentLobby.IsValid())
            return false;
        uint64_t my_id = SteamUser()->GetSteamID().ConvertToUint64();
        auto members = get_lobby_members();
        bool all_ok = true;
        for (uint64_t member : members)
        {
            if (member != my_id)
            {
                if (!send_message(member, data, reliable, channel))
                {
                    all_ok = false;
                }
            }
        }
        return all_ok;
    }

    // ============ Polling (Python her frame bunu çağırır) ============

    void run_callbacks()
    {
        if (m_isShutdown)
            return;
        // Steam callback'lerini işle
        SteamAPI_RunCallbacks();

        // Gelen ağ mesajlarını TÜM kanallardan kuyruğa al
        // CHANNEL_GAME=0, CHANNEL_STATE=1, CHANNEL_CONTROL=2
        _poll_incoming_messages(0);
        _poll_incoming_messages(1);
        _poll_incoming_messages(2);
    }

    std::vector<NetEvent> poll_events()
    {
        std::lock_guard<std::mutex> lock(m_eventMutex);
        std::vector<NetEvent> result(m_events.begin(), m_events.end());
        m_events.clear();
        return result;
    }

    std::vector<NetMessage> poll_messages()
    {
        std::lock_guard<std::mutex> lock(m_msgMutex);
        std::vector<NetMessage> result(m_messages_queue.begin(), m_messages_queue.end());
        m_messages_queue.clear();
        return result;
    }

    // ============ Yardımcı ============

    uint64_t get_my_steam_id()
    {
        if (m_isShutdown)
            return 0;
        return SteamUser() ? SteamUser()->GetSteamID().ConvertToUint64() : 0;
    }

    std::string get_friend_persona_name(uint64_t steam_id)
    {
        if (!m_friends || m_isShutdown)
            return "";
        CSteamID sid(steam_id);
        const char *name = m_friends->GetFriendPersonaName(sid);
        return name ? std::string(name) : "";
    }

private:
    ISteamMatchmaking *m_matchmaking;
    ISteamNetworkingMessages *m_messages;
    ISteamFriends *m_friends;
    CSteamID m_currentLobby;
    bool m_lobbyReady;
    // join_requested'dan itibaren geçen süreyi ölçmek için (epoch saniye)
    uint32 m_joinRequestedTime;
    bool m_lobbyListRequestActive;
    std::vector<uint64_t> m_pendingLobbyDataRequests;
    std::unordered_map<uint64_t, int> m_pendingLobbyDataRetryCounts;
    std::string m_pendingLobbyVisibility;
    bool m_pendingLobbyRequiresCode;
    bool m_isShutdown;

    // Event kuyruğu
    std::mutex m_eventMutex;
    std::deque<NetEvent> m_events;

    // Message kuyruğu
    std::mutex m_msgMutex;
    std::deque<NetMessage> m_messages_queue;

    // CCallResult'lar (asenkron Steam API çağrıları için)
    CCallResult<SteamNetBridge, LobbyCreated_t> m_lobbyCreatedResult;
    CCallResult<SteamNetBridge, LobbyEnter_t> m_lobbyEnterResult;
    CCallResult<SteamNetBridge, LobbyMatchList_t> m_lobbyListResult;

    // Steam Callback'ler (otomatik — CCallback)
    STEAM_CALLBACK(SteamNetBridge, OnLobbyChatUpdate, LobbyChatUpdate_t);
    STEAM_CALLBACK(SteamNetBridge, OnLobbyDataUpdate, LobbyDataUpdate_t);
    STEAM_CALLBACK(SteamNetBridge, OnGameLobbyJoinRequested, GameLobbyJoinRequested_t);
    STEAM_CALLBACK(SteamNetBridge, OnSessionRequest, SteamNetworkingMessagesSessionRequest_t);

    // ---------- Yardımcı iç fonksiyonlar ----------

    void push_event(const std::string &type, uint64_t steam_id, const std::string &data)
    {
        std::lock_guard<std::mutex> lock(m_eventMutex);
        m_events.push_back({type, steam_id, data});
    }

    static constexpr int kMaxLobbyDataRequestRetries = 5;

    void set_pending_lobby_metadata(ELobbyType lobbyType)
    {
        if (lobbyType == k_ELobbyTypePublic)
        {
            m_pendingLobbyVisibility = "public";
            m_pendingLobbyRequiresCode = false;
            return;
        }

        // Invisible ve FriendsOnly lobileri de özel lobi olarak işle
        // (kod ile girilebilir, public listede görünmez)
        m_pendingLobbyVisibility = "private";
        m_pendingLobbyRequiresCode = true;
    }

    static std::string json_escape(const std::string &value)
    {
        std::string escaped;
        escaped.reserve(value.size());
        for (unsigned char ch : value)
        {
            switch (ch)
            {
            case '\\':
                escaped += "\\\\";
                break;
            case '"':
                escaped += "\\\"";
                break;
            case '\n':
                escaped += "\\n";
                break;
            case '\r':
                escaped += "\\r";
                break;
            case '\t':
                escaped += "\\t";
                break;
            case '\b':
                escaped += "\\b";
                break;
            case '\f':
                escaped += "\\f";
                break;
            default:
                if (ch < 0x20)
                {
                    // JSON spec: control characters must be escaped as \uXXXX
                    char buf[8];
                    snprintf(buf, sizeof(buf), "\\u%04x", ch);
                    escaped += buf;
                }
                else
                {
                    escaped += static_cast<char>(ch);
                }
                break;
            }
        }
        return escaped;
    }

    std::string build_lobby_found_payload(CSteamID lobbyId)
    {
        if (!m_matchmaking)
            return "{}";
        const char *hostNameRaw = m_matchmaking->GetLobbyData(lobbyId, "host_name");
        const char *lobbyCodeRaw = m_matchmaking->GetLobbyData(lobbyId, "lobby_code");
        const char *visibilityRaw = m_matchmaking->GetLobbyData(lobbyId, "visibility");
        const char *requiresCodeRaw = m_matchmaking->GetLobbyData(lobbyId, "requires_code");
        const char *metadataReadyRaw = m_matchmaking->GetLobbyData(lobbyId, "metadata_ready");

        std::string hostName = hostNameRaw ? hostNameRaw : "";
        std::string lobbyCode = lobbyCodeRaw ? lobbyCodeRaw : "";
        bool hasVisibility = visibilityRaw && visibilityRaw[0] != '\0';
        bool hasRequiresCode = requiresCodeRaw && requiresCodeRaw[0] != '\0';
        bool hasMetadataReady = metadataReadyRaw && metadataReadyRaw[0] != '\0';

        // visibility & requires_code: metadata varsa olduğu gibi geç,
        // yoksa JSON null olarak gönder — Python live read ile ikinci şans verir.
        // Böylece henüz propague olmamış metadata "private" varsayılmaz.
        std::string visibilityJson;
        std::string requiresCodeJson;
        std::string metadataReadyJson = "null";

        if (hasMetadataReady)
        {
            bool ready = std::string(metadataReadyRaw) == "1";
            metadataReadyJson = ready ? "true" : "false";
        }

        if (hasVisibility)
        {
            std::string vis(visibilityRaw);
            visibilityJson = "\"" + json_escape(vis) + "\"";

            if (hasRequiresCode)
            {
                bool rc = std::string(requiresCodeRaw) == "1";
                requiresCodeJson = rc ? "true" : "false";
            }
            else
            {
                // visibility var, requires_code yok — türet
                requiresCodeJson = (vis == "public") ? "false" : "true";
            }
        }
        else if (hasRequiresCode)
        {
            bool rc = std::string(requiresCodeRaw) == "1";
            visibilityJson = rc ? "\"private\"" : "\"public\"";
            requiresCodeJson = rc ? "true" : "false";
        }
        else if (!lobbyCode.empty())
        {
            // Sadece lobby_code var — private olarak türet
            visibilityJson = "\"private\"";
            requiresCodeJson = "true";
        }
        else
        {
            // Hiçbir metadata yok — null gönder, Python live read denesin
            visibilityJson = "null";
            requiresCodeJson = "null";
        }

        return std::string("{") +
               "\"members\":" + std::to_string(m_matchmaking->GetNumLobbyMembers(lobbyId)) +
               ",\"max_members\":" + std::to_string(m_matchmaking->GetLobbyMemberLimit(lobbyId)) +
               ",\"host_name\":\"" + json_escape(hostName) + "\"" +
               ",\"lobby_code\":\"" + json_escape(lobbyCode) + "\"" +
               ",\"visibility\":" + visibilityJson +
               ",\"requires_code\":" + requiresCodeJson +
               ",\"metadata_ready\":" + metadataReadyJson +
               "}";
    }

    void emit_lobby_found(CSteamID lobbyId)
    {
        push_event("lobby_found", lobbyId.ConvertToUint64(), build_lobby_found_payload(lobbyId));
    }

    bool has_pending_lobby_data_request(uint64_t lobbyId) const
    {
        return std::find(
                   m_pendingLobbyDataRequests.begin(),
                   m_pendingLobbyDataRequests.end(),
                   lobbyId) != m_pendingLobbyDataRequests.end();
    }

    void remember_pending_lobby_data_request(uint64_t lobbyId)
    {
        if (!has_pending_lobby_data_request(lobbyId))
        {
            m_pendingLobbyDataRequests.push_back(lobbyId);
        }
        m_pendingLobbyDataRetryCounts[lobbyId] = 0;
    }

    bool is_lobby_metadata_ready_for_listing(CSteamID lobbyId) const
    {
        if (!m_matchmaking)
        {
            return false;
        }

        const char *metadataReadyRaw = m_matchmaking->GetLobbyData(lobbyId, "metadata_ready");
        if (metadataReadyRaw && metadataReadyRaw[0] != '\0')
        {
            return std::string(metadataReadyRaw) == "1";
        }

        const char *visibilityRaw = m_matchmaking->GetLobbyData(lobbyId, "visibility");
        if (visibilityRaw && visibilityRaw[0] != '\0')
        {
            return true;
        }

        const char *requiresCodeRaw = m_matchmaking->GetLobbyData(lobbyId, "requires_code");
        if (requiresCodeRaw && requiresCodeRaw[0] != '\0')
        {
            return true;
        }

        const char *lobbyCodeRaw = m_matchmaking->GetLobbyData(lobbyId, "lobby_code");
        return lobbyCodeRaw && lobbyCodeRaw[0] != '\0';
    }

    bool retry_pending_lobby_data_request(CSteamID lobbyId)
    {
        if (!m_matchmaking || m_isShutdown)
        {
            return false;
        }

        uint64_t lobbyIdValue = lobbyId.ConvertToUint64();
        auto it = m_pendingLobbyDataRetryCounts.find(lobbyIdValue);
        if (it == m_pendingLobbyDataRetryCounts.end())
        {
            return false;
        }
        if (it->second >= kMaxLobbyDataRequestRetries)
        {
            return false;
        }

        it->second += 1;
        return m_matchmaking->RequestLobbyData(lobbyId);
    }

    bool consume_pending_lobby_data_request(uint64_t lobbyId)
    {
        auto it = std::find(m_pendingLobbyDataRequests.begin(), m_pendingLobbyDataRequests.end(), lobbyId);
        if (it == m_pendingLobbyDataRequests.end())
        {
            return false;
        }
        m_pendingLobbyDataRequests.erase(it);
        m_pendingLobbyDataRetryCounts.erase(lobbyId);
        return true;
    }

    void complete_lobby_list_if_ready()
    {
        if (m_lobbyListRequestActive && m_pendingLobbyDataRequests.empty())
        {
            m_lobbyListRequestActive = false;
            push_event("lobby_list_complete", 0, "");
        }
    }

    void _poll_incoming_messages(int channel = 0)
    {
        if (!m_messages || m_isShutdown)
            return;
        while (true)
        {
            SteamNetworkingMessage_t *pMessages[64];
            int count = m_messages->ReceiveMessagesOnChannel(channel, pMessages, 64);
            if (count <= 0)
                break;

            {
                std::lock_guard<std::mutex> lock(m_msgMutex);
                for (int i = 0; i < count; i++)
                {
                    NetMessage msg;
                    msg.sender = pMessages[i]->m_identityPeer.GetSteamID64();
                    msg.payload = std::string(
                        (const char *)pMessages[i]->m_pData,
                        pMessages[i]->m_cbSize);
                    msg.channel = channel;
                    m_messages_queue.push_back(std::move(msg));
                    pMessages[i]->Release();
                }
            }

            if (count < 64)
                break;
        }
    }

    // ---------- Callback Handlers ----------

    void OnLobbyCreated(LobbyCreated_t *pResult, bool bIOFailure)
    {
        if (bIOFailure || pResult->m_eResult != k_EResultOK)
        {
            std::string errorData = std::string("result=") + std::to_string((int)pResult->m_eResult) +
                                    ",visibility=" + m_pendingLobbyVisibility +
                                    ",requires_code=" + (m_pendingLobbyRequiresCode ? std::string("1") : std::string("0"));
            push_event("lobby_create_failed", 0,
                       errorData);
            return;
        }
        m_currentLobby = CSteamID(pResult->m_ulSteamIDLobby);
        m_lobbyReady = true;

        // Sadece temel keşif metadata'sını yaz.
        // visibility, requires_code, lobby_code gibi hassas alanlar
        // Python tarafından (_on_lobby_created) yazılır. Böylece
        // "C++ public yazar → diğer platform okur → Python private
        // override yapar" şeklinde bir race window önlenir.
        // metadata_ready=0 olarak işaretle; Python tüm alanları
        // doğru şekilde yazdıktan sonra metadata_ready=1 yapacak.
        m_matchmaking->SetLobbyData(m_currentLobby, "game", "quadrix");
        m_matchmaking->SetLobbyData(m_currentLobby, "version", "1.0");
        if (m_friends)
        {
            const char *personaName = m_friends->GetPersonaName();
            if (personaName && personaName[0] != '\0')
            {
                m_matchmaking->SetLobbyData(m_currentLobby, "host_name", personaName);
            }
        }
        m_matchmaking->SetLobbyData(m_currentLobby, "metadata_ready", "0");
        m_matchmaking->SetLobbyJoinable(m_currentLobby, true);

        push_event("lobby_created", pResult->m_ulSteamIDLobby, "");
    }

    void OnLobbyEnter(LobbyEnter_t *pResult, bool bIOFailure)
    {
        if (bIOFailure || pResult->m_EChatRoomEnterResponse != k_EChatRoomEnterResponseSuccess)
        {
            push_event("lobby_join_failed", pResult->m_ulSteamIDLobby,
                       "Giris kodu: " + std::to_string(pResult->m_EChatRoomEnterResponse));
            return;
        }
        m_currentLobby = CSteamID(pResult->m_ulSteamIDLobby);
        m_lobbyReady = true;

        // Cross-platform metadata propagasyonu: lobiye katıldıktan sonra
        // metadata'yı açıkça iste. macOS→Windows arası metadata
        // otomatik olarak önbelleğe alınmayabilir; RequestLobbyData,
        // callback tetikleyerek güncel metadata'nın Python'a ulaşmasını sağlar.
        if (m_matchmaking)
        {
            m_matchmaking->RequestLobbyData(m_currentLobby);
        }

        // lobby_joined event'ini metadata snapshot'ı ile gönder.
        // Böylece Python tarafı katılım anında mevcut metadata'yı
        // doğrudan kullanabilir (ayrıca RequestLobbyData callback'i ile
        // güncel veri de gelecek).
        push_event("lobby_joined", pResult->m_ulSteamIDLobby,
                   build_lobby_found_payload(m_currentLobby));
    }

    void OnLobbyListReceived(LobbyMatchList_t *pResult, bool bIOFailure)
    {
        if (bIOFailure)
        {
            m_lobbyListRequestActive = false;
            m_pendingLobbyDataRequests.clear();
            m_pendingLobbyDataRetryCounts.clear();
            push_event("lobby_list_failed", 0, "IO hatasi");
            return;
        }
        m_lobbyListRequestActive = false;
        m_pendingLobbyDataRequests.clear();
        m_pendingLobbyDataRetryCounts.clear();

        // Listeyi Steam'in ek metadata callback'lerine bağlama.
        // Bazi live lobi kayitlari RequestLobbyData callback'ini hic getirmiyor,
        // bu da Python tarafinda tum listenin sonsuza kadar "yukleniyor"
        // kalmasina neden oluyor. Mevcut snapshot'i hemen yayinla;
        // metadata gelirse arka planda lobby_data_updated ile tazelenecek.
        for (uint32 i = 0; i < pResult->m_nLobbiesMatching; i++)
        {
            CSteamID lobbyId = m_matchmaking->GetLobbyByIndex(i);
            emit_lobby_found(lobbyId);
            if (m_matchmaking->RequestLobbyData(lobbyId))
            {
                remember_pending_lobby_data_request(lobbyId.ConvertToUint64());
            }
        }
        push_event("lobby_list_complete", 0, "");
    }
};

// ---------- Otomatik Callback Implementasyonları ----------

void SteamNetBridge::OnLobbyChatUpdate(LobbyChatUpdate_t *pParam)
{
    if (m_isShutdown)
        return;
    uint64_t changed_id = pParam->m_ulSteamIDUserChanged;
    uint32 state = pParam->m_rgfChatMemberStateChange;
    std::string state_info = std::to_string(state);

    if (state & k_EChatMemberStateChangeEntered)
    {
        std::string name = m_friends
                               ? m_friends->GetFriendPersonaName(CSteamID(changed_id))
                               : "";
        push_event("lobby_member_joined", changed_id, name);
    }
    if (state & k_EChatMemberStateChangeLeft)
    {
        push_event("lobby_member_left", changed_id, state_info);
    }
    if (state & k_EChatMemberStateChangeDisconnected)
    {
        push_event("lobby_member_disconnected", changed_id, state_info);
    }
}

void SteamNetBridge::OnLobbyDataUpdate(LobbyDataUpdate_t *pParam)
{
    if (m_isShutdown)
        return;
    CSteamID lobbyId(pParam->m_ulSteamIDLobby);
    uint64_t lobbyIdValue = lobbyId.ConvertToUint64();
    bool hasPendingRequest = has_pending_lobby_data_request(lobbyIdValue);

    if (!pParam->m_bSuccess)
    {
        if (hasPendingRequest && retry_pending_lobby_data_request(lobbyId))
        {
            return;
        }
        consume_pending_lobby_data_request(lobbyIdValue);
        return;
    }

    if (hasPendingRequest && !is_lobby_metadata_ready_for_listing(lobbyId))
    {
        if (retry_pending_lobby_data_request(lobbyId))
        {
            // Retry başarılı — daha sonra tekrar callback gelecek.
            // Yine de mevcut durumu Python'a bildir (JSON payload ile).
            push_event("lobby_data_updated",
                       pParam->m_ulSteamIDLobby,
                       build_lobby_found_payload(lobbyId));
            return;
        }
        // Retry hakkı doldu — mevcut snapshot'ı gönder
    }

    if (hasPendingRequest)
    {
        consume_pending_lobby_data_request(lobbyIdValue);
    }

    // Metadata güncellemesini Python'a bildir.
    // Ayrıca lobinin güncel metadata snapshot'ını da gönder;
    // Python tarafı live-read yapmak yerine bu payload'ı kullanabilir.
    push_event("lobby_data_updated",
               pParam->m_ulSteamIDLobby,
               build_lobby_found_payload(lobbyId));
}

void SteamNetBridge::OnGameLobbyJoinRequested(GameLobbyJoinRequested_t *pParam)
{
    if (m_isShutdown)
        return;
    // Kullanıcı Steam overlay'den "Oyuna Katıl" dedi
    // Allowlist penceresini başlat (lobby yokken 30s kabul)
    m_joinRequestedTime = SteamUtils() ? SteamUtils()->GetServerRealTime() : 0;
    push_event("join_requested", pParam->m_steamIDLobby.ConvertToUint64(),
               std::to_string(pParam->m_steamIDFriend.ConvertToUint64()));
}

void SteamNetBridge::OnSessionRequest(SteamNetworkingMessagesSessionRequest_t *pParam)
{
    if (!m_messages || m_isShutdown)
        return;

    uint64_t remote_id = pParam->m_identityRemote.GetSteamID64();

    if (m_currentLobby.IsValid() && m_currentLobby != k_steamIDNil)
    {
        // Lobby geçerli: sadece lobby üyelerini kabul et
        bool is_member = false;
        if (m_matchmaking)
        {
            int count = m_matchmaking->GetNumLobbyMembers(m_currentLobby);
            for (int i = 0; i < count; i++)
            {
                CSteamID member = m_matchmaking->GetLobbyMemberByIndex(m_currentLobby, i);
                if (member.ConvertToUint64() == remote_id)
                {
                    is_member = true;
                    break;
                }
            }
        }
        if (!is_member)
        {
            push_event("session_rejected", remote_id, "not_lobby_member");
            return;
        }
    }
    else
    {
        // Lobby yok: join_requested'dan itibaren 30 saniyelik allowlist penceresi
        uint32 now = SteamUtils() ? SteamUtils()->GetServerRealTime() : 0;
        bool in_window = (m_joinRequestedTime > 0) &&
                         (now >= m_joinRequestedTime) &&
                         ((now - m_joinRequestedTime) <= 30u);
        if (!in_window)
        {
            push_event("session_rejected", remote_id, "no_lobby_no_window");
            return;
        }
    }

    m_messages->AcceptSessionWithUser(pParam->m_identityRemote);
    push_event("session_accepted", remote_id, "");
}

// ============ Pybind11 Modül Tanımı ============

PYBIND11_MODULE(steam_net_bridge, m)
{
    m.doc() = "Quadrix Steam Networking Bridge — Lobi & P2P mesajlaşma";

    py::class_<NetEvent>(m, "NetEvent")
        .def_readonly("type", &NetEvent::type)
        .def_readonly("steam_id", &NetEvent::steam_id)
        .def_readonly("data", &NetEvent::data)
        .def("__repr__", [](const NetEvent &e)
             { return "<NetEvent type='" + e.type + "' steam_id=" +
                      std::to_string(e.steam_id) + " data='" + e.data + "'>"; });

    py::class_<NetMessage>(m, "NetMessage")
        .def_readonly("sender", &NetMessage::sender)
        .def_readonly("payload", &NetMessage::payload)
        .def_readonly("channel", &NetMessage::channel)
        .def("__repr__", [](const NetMessage &msg)
             { return "<NetMessage sender=" + std::to_string(msg.sender) +
                      " size=" + std::to_string(msg.payload.size()) + ">"; });

    py::class_<SteamNetBridge>(m, "SteamNetBridge")
        .def(py::init<>())
        .def("init", &SteamNetBridge::init)
        .def("shutdown", &SteamNetBridge::shutdown)
        // Lobi
        .def("create_lobby", &SteamNetBridge::create_lobby, py::arg("max_members") = 2)
        .def("create_public_lobby", &SteamNetBridge::create_public_lobby, py::arg("max_members") = 2)
        .def("join_lobby", &SteamNetBridge::join_lobby, py::arg("lobby_id"))
        .def("leave_lobby", &SteamNetBridge::leave_lobby)
        .def("set_lobby_data", &SteamNetBridge::set_lobby_data)
        .def("get_lobby_data", &SteamNetBridge::get_lobby_data)
        .def("get_lobby_data_for", &SteamNetBridge::get_lobby_data_for,
             py::arg("lobby_id"), py::arg("key"))
        .def("get_lobby_members", &SteamNetBridge::get_lobby_members)
        .def("get_lobby_owner", &SteamNetBridge::get_lobby_owner)
        .def("get_current_lobby_id", &SteamNetBridge::get_current_lobby_id)
        .def("is_in_lobby", &SteamNetBridge::is_in_lobby)
        .def("invite_friend", &SteamNetBridge::invite_friend)
        .def("create_lobby_with_type", &SteamNetBridge::create_lobby_with_type,
             py::arg("lobby_type"), py::arg("max_members") = 2)
        .def("set_lobby_type", &SteamNetBridge::set_lobby_type,
             py::arg("lobby_type"))
        .def("set_lobby_joinable", &SteamNetBridge::set_lobby_joinable,
             py::arg("joinable"))
        .def("add_request_lobby_list_string_filter",
             &SteamNetBridge::add_request_lobby_list_string_filter,
             py::arg("key"), py::arg("value"))
        .def("add_request_lobby_list_distance_filter",
             &SteamNetBridge::add_request_lobby_list_distance_filter,
             py::arg("distance_filter"))
        .def("request_lobby_list", &SteamNetBridge::request_lobby_list)
        .def("request_lobby_data", &SteamNetBridge::request_lobby_data,
             py::arg("lobby_id"))
        // Mesajlaşma
        .def("send_message", &SteamNetBridge::send_message,
             py::arg("target_steam_id"), py::arg("data"),
             py::arg("reliable") = true, py::arg("channel") = 0)
        .def("send_message_to_lobby", &SteamNetBridge::send_message_to_lobby,
             py::arg("data"), py::arg("reliable") = true, py::arg("channel") = 0)
        // Polling
        .def("run_callbacks", &SteamNetBridge::run_callbacks)
        .def("poll_events", &SteamNetBridge::poll_events)
        .def("poll_messages", &SteamNetBridge::poll_messages)
        // Yardımcı
        .def("get_my_steam_id", &SteamNetBridge::get_my_steam_id)
        .def("get_friend_persona_name", &SteamNetBridge::get_friend_persona_name);
}
