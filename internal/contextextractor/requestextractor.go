package contextextractor

import (
	"fmt"
	"log"
	"net"
	"net/http"
	"net/netip"
	"strings"

	lru "github.com/hashicorp/golang-lru"
	"github.com/oschwald/geoip2-golang/v2"
	"github.com/ua-parser/uap-go/uaparser"
)

type GeoInfo struct {
	Country string
	City    string
	Lat     float64
	Lon     float64
}

type DeviceInfo struct {
	Device string
	OS     string
}

type RequestContext struct {
	IP       string
	Geo      GeoInfo
	Device   DeviceInfo
	Language string
}

var geoDB *geoip2.Reader
var uaParser *uaparser.Parser
var ipGeoLRU *lru.Cache

func InitRequestExtractorDB() {
	var err error

	geoDB, err = geoip2.Open("./internal/contextextractor/config/GeoLite2-City.mmdb")
	if err != nil {
		log.Printf("Warning: failed to load GeoLite2-City: %v. Geo lookups will be disabled.", err)
		geoDB = nil
	}

	uaParser, err = uaparser.New("./internal/contextextractor/config/regexes.yaml")
	if err != nil {
		log.Printf("Warning: failed to initialize UA parser: %v. Using fallback user agent parsing.", err)
		uaParser = nil
	}

	ipGeoLRU, _ = lru.New(10000)
}

func RetrieveRequestContext(r *http.Request) RequestContext {
	ip := getClientIP(r)

	// Allow geo country override via header (for traffic simulation / testing)
	var geo GeoInfo
	if countryOverride := r.Header.Get("X-Geo-Country"); countryOverride != "" {
		geo = GeoInfo{Country: countryOverride}
	} else {
		geo = extractGeo(ip)
	}

	device := extractDevice(r)
	lang := extractLanguage(r)

	return RequestContext{
		IP:       ip,
		Geo:      geo,
		Device:   device,
		Language: lang,
	}
}

func extractLanguage(r *http.Request) string {
	langHeader := r.Header.Get("Accept-Language")
	if langHeader == "" {
		return "en"
	}
	parts := strings.Split(langHeader, ",")
	primary := strings.TrimSpace(parts[0])
	if len(primary) >= 2 {
		return primary[:2]
	}
	return "en"
}

func extractDevice(r *http.Request) DeviceInfo {
	ua := r.Header.Get("User-Agent")

	deviceType := "desktop"
	if strings.Contains(strings.ToLower(ua), "mobile") {
		deviceType = "mobile"
	}

	// Handle case where UA parser failed to initialize
	if uaParser == nil {
		return DeviceInfo{
			Device: deviceType,
			OS:     "unknown",
		}
	}

	client := uaParser.Parse(ua)

	return DeviceInfo{
		Device: deviceType,
		OS:     client.Os.Family,
	}
}

func extractGeo(ip string) GeoInfo {
	if ipGeoLRU != nil {
		if value, found := ipGeoLRU.Get(ip); found {
			if geoInfo, ok := value.(*GeoInfo); ok {
				return *geoInfo
			}
		}
	}
	record, _, err := LookupGeo(ip)
	if err != nil {
		return GeoInfo{}
	}

	geoInfo := GeoInfo{}

	if !record.HasData() {
		fmt.Println("No data found for this IP")
		return geoInfo
	}

	if record.Location.HasCoordinates() {
		if record.Location.Latitude != nil {
			geoInfo.Lat = *record.Location.Latitude
		}
		if record.Location.Longitude != nil {
			geoInfo.Lon = *record.Location.Longitude
		}
	}
	geoInfo.Country = record.Country.ISOCode
	geoInfo.City = record.City.Names.English

	if ipGeoLRU != nil {
		ipGeoLRU.Add(ip, &geoInfo)
	}

	return geoInfo
}

func LookupGeo(ipStr string) (*geoip2.City, netip.Addr, error) {
	if geoDB == nil {
		return nil, netip.Addr{}, fmt.Errorf("geo database not initialized")
	}

	ip, err := netip.ParseAddr(ipStr)
	if err != nil {
		return nil, netip.Addr{}, fmt.Errorf("invalid IP address: %v", err)
	}

	record, err := geoDB.City(ip)
	return record, ip, err
}

func getClientIP(r *http.Request) string {
	xff := r.Header.Get("X-Forwarded-For")
	if xff != "" {
		parts := strings.Split(xff, ",")
		ip := strings.TrimSpace(parts[0])
		if net.ParseIP(ip) != nil {
			return ip
		}
	}

	xRealIP := r.Header.Get("X-Real-IP")
	if net.ParseIP(xRealIP) != nil {
		return xRealIP
	}

	host, _, err := net.SplitHostPort(r.RemoteAddr)
	if err == nil && net.ParseIP(host) != nil {
		return host
	}

	return ""
}
