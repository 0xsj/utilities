package main

import (
	"flag"
	"fmt"
	"io/ioutil"
	"net/http"
	"net/url"
	"strings"
	"sync"
	"time"
)

func main() {
	baseURL := flag.String("url", "https://cad-backend-dev-l2yi2.ondigitalocean.app/api/incidents", "Base URL to test")
	numRequests := flag.Int("n", 100, "Number of requests to send")
	concurrency := flag.Int("c", 10, "Number of concurrent requests")
	timeout := flag.Int("t", 5, "Timeout in seconds")
	delay := flag.Int("d", 0, "Delay between requests in milliseconds (per worker)")
	debugFlag := flag.Bool("debug", false, "Show detailed debug info")
	flag.Parse()

	authToken := "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmdWxsTmFtZSI6IlN1cGVyIEFkbWluIiwiaXNTdGFmZiI6dHJ1ZSwiaXNBZG1pbiI6ZmFsc2UsImFyY2hpdmVkIjpmYWxzZSwiaW5pdGlhbHMiOiJTVVAiLCJpZCI6InN1cGVyQWRtaW4iLCJmaXJzdE5hbWUiOiJTdXBlciIsImxhc3ROYW1lIjoiQWRtaW4iLCJwZW5kaW5nIjpmYWxzZSwiYXJjaGl2ZWRBdCI6bnVsbCwiZW1haWwiOiJzdXBlcmFkbWluQG5ha2VkZGV2LmNvbSIsImFsZXJ0X2VtYWlsIjpudWxsLCJlbWFpbEFsZXJ0cyI6ZmFsc2UsInZhY2F0aW9uTW9kZSI6ZmFsc2UsInRlbXBBdXRoVG9rZW4iOm51bGwsInBob25lIjoiMzEzMjQ4NTM2OSIsInNob3J0TmFtZSI6IlNVUCIsImxvY2F0aW9uIjpudWxsLCJmaXJzdExvZ2luQXQiOiIyMDI1LTA0LTA2VDEyOjQ1OjM4LjAwMFoiLCJsYXN0TG9naW5BdCI6IjIwMjUtMDQtMjhUMjM6NTk6MzcuNDU4WiIsImNyZWF0ZWRBdCI6IjIwMjMtMDctMTNUMDA6NTU6MjcuMDAwWiIsInVwZGF0ZWRBdCI6IjIwMjUtMDQtMjhUMjM6NTk6MzcuNDU4WiIsIkJ1c2luZXNzSWQiOm51bGwsIkF2YXRhcklkIjpudWxsLCJBdmF0YXIiOm51bGwsIkJ1c2luZXNzIjpudWxsLCJSb2xlcyI6W3siaWQiOiJzdXBlckFkbWluIiwibmFtZSI6IlN1cGVyIEFkbWluIiwiaXNTdGFmZiI6dHJ1ZX1dLCJpYXQiOjE3NDU4ODQ3Nzd9.SjGl-YN7aEMnaTfNPpODBDZVHw5BuHzvyo9kXSwElZY"

	fmt.Printf("Starting load test against %s\n", *baseURL)
	fmt.Printf("Sending %d requests with %d concurrent workers\n", *numRequests, *concurrency)
	
	presets := "COMMERCIAL | DETACHED BLDG FIRE,COMMERCIAL | ELECTRICAL,COMMERCIAL | EXPLOSION,COMMERCIAL | FIRE,COMMERCIAL | FLOODING UNCONFIRMED,COMMERCIAL | FOOD-COOKING,COMMERCIAL | HAZMAT,COMMERCIAL | INDOOR WATER,COMMERCIAL | INVESTIGATION,COMMERCIAL | LIVE UPDATE TEST,COMMERCIAL | MISC STRUCTURE DAMAGE,COMMERCIAL | OUTDOOR FIRE NO EXPOSURES,COMMERCIAL | OUTDOOR FIRE WITH EXPOSURES,COMMERCIAL | SMOKE FIRE OUT,COMMERCIAL | UDPATE-V2,COMMERCIAL | VEHICLE INTO BLDG,HOUSE | DETACHED BLDG FIRE,HOUSE | ELECTRICAL,HOUSE | EVENT-LISTERNER,HOUSE | EXPLOSION,HOUSE | FIRE,HOUSE | FLOODING UNCONFIRMED,HOUSE | FOOD-COOKING,HOUSE | HAZMAT,HOUSE | INDOOR WATER,HOUSE | INVESTIGATION,HOUSE | MISC STRUCTURE DAMAGE,HOUSE | OUTDOOR FIRE NO EXPOSURES,HOUSE | OUTDOOR FIRE WITH EXPOSURES,HOUSE | SMOKE FIRE OUT,HOUSE | VEHICLE INTO BLDG,MOBILE HOME | DETACHED BLDG FIRE,MOBILE HOME | ELECTRICAL,MOBILE HOME | EXPLOSION,MOBILE HOME | FIRE,MOBILE HOME | FLOODING UNCONFIRMED,MOBILE HOME | FOOD-COOKING,MOBILE HOME | HAZMAT,MOBILE HOME | INDOOR WATER,MOBILE HOME | INVESTIGATION,MOBILE HOME | MISC STRUCTURE DAMAGE,MOBILE HOME | OUTDOOR FIRE NO EXPOSURES,MOBILE HOME | OUTDOOR FIRE WITH EXPOSURES,MOBILE HOME | SMOKE FIRE OUT,MOBILE HOME | VEHICLE INTO BLDG,MULTIFAMILY | DETACHED BLDG FIRE,MULTIFAMILY | ELECTRICAL,MULTIFAMILY | EXPLOSION,MULTIFAMILY | FIRE,MULTIFAMILY | FLOODING UNCONFIRMED,MULTIFAMILY | FOOD-COOKING,MULTIFAMILY | HAZMAT,MULTIFAMILY | INDOOR WATER,MULTIFAMILY | INVESTIGATION,MULTIFAMILY | MISC STRUCTURE DAMAGE,MULTIFAMILY | OUTDOOR FIRE NO EXPOSURES,MULTIFAMILY | OUTDOOR FIRE WITH EXPOSURES,MULTIFAMILY | SMOKE FIRE OUT,MULTIFAMILY | VEHICLE INTO BLDG,OTHER | EARTHQUAKE,OTHER | MARINE - BOAT IN WATER,OTHER | NEWS,OTHER | STREET,OTHER | TEST,OTHER | TRAFFIC COLLISION,OTHER | WEATHER,OUTDOOR | BRUSH FIRE - NO STRUCTURE INVOLVEMENT,OUTDOOR | BRUSH FIRE - STRUCTURE INVOLVEMENT,OUTDOOR | FIRE,OUTDOOR | WATER - NO STRUCTURE INVOLVEMENT - THREAT,OUTDOOR | WATER - STRUCTURE INVOLVEMENT - THREAT"

	client := &http.Client{
		Timeout: time.Duration(*timeout) * time.Second,
	}

	var (
		wg              sync.WaitGroup
		successCount    int
		failCount       int
		timeoutCount    int
		socketHangUps   int
		statusCodeCount map[int]int
		mutex           sync.Mutex
		responseData    string
	)
	
	statusCodeCount = make(map[int]int)

	semaphore := make(chan struct{}, *concurrency)

	startTime := time.Now()

	for i := 0; i < *numRequests; i++ {
		wg.Add(1)
		semaphore <- struct{}{} 

		go func(requestNum int) {
			defer wg.Done()
			defer func() { <-semaphore }() 

			u, err := url.Parse(*baseURL)
			if err != nil {
				fmt.Printf("Error parsing URL: %v\n", err)
				return
			}
			
			q := u.Query()
			q.Add("from", "2025-04-28 18:35:32")
			q.Add("to", "2025-04-29 23:59:59")
			q.Add("presets", presets)
			q.Add("location", "")
			q.Add("keywords", "")
			q.Add("category", "all")
			q.Add("limit", "50")
			q.Add("after", "")
			u.RawQuery = q.Encode()

			req, err := http.NewRequest("GET", u.String(), nil)
			if err != nil {
				fmt.Printf("Error creating request: %v\n", err)
				return
			}

			req.Header.Add("Authorization", fmt.Sprintf("Bearer %s", authToken))
			req.Header.Add("Content-Type", "application/json")

			if *delay > 0 && requestNum > 0 {
				time.Sleep(time.Duration(*delay) * time.Millisecond)
			}

			start := time.Now()
			resp, err := client.Do(req)
			duration := time.Since(start)

			mutex.Lock()
			if err != nil {
				failCount++
				if strings.Contains(err.Error(), "timeout") || 
				   strings.Contains(err.Error(), "deadline exceeded") {
					timeoutCount++
					fmt.Printf("Request %d timed out after %.2fs: %v\n", requestNum, duration.Seconds(), err)
				} else if strings.Contains(err.Error(), "socket hang up") || 
				         strings.Contains(err.Error(), "connection reset") ||
						 strings.Contains(err.Error(), "ECONNRESET") {
					socketHangUps++
					fmt.Printf("Request %d socket hang up after %.2fs: %v\n", requestNum, duration.Seconds(), err)
				} else {
					fmt.Printf("Request %d failed after %.2fs: %v\n", requestNum, duration.Seconds(), err)
				}
			} else {
				if requestNum == 0 || *debugFlag {
					bodyBytes, _ := ioutil.ReadAll(resp.Body)
					bodyText := string(bodyBytes)
					if requestNum == 0 {
						responseData = bodyText
					}
					resp.Body.Close()
				} else {
					resp.Body.Close() 
				}
				
				successCount++
				statusCodeCount[resp.StatusCode]++
				fmt.Printf("Request %d completed in %.2fs with status: %d\n", requestNum, duration.Seconds(), resp.StatusCode)
			}
			mutex.Unlock()
		}(i)
	}

	wg.Wait()
	totalDuration := time.Since(startTime)

	fmt.Println("\n--- Test Results ---")
	fmt.Printf("Total time: %.2fs\n", totalDuration.Seconds())
	fmt.Printf("Successful requests: %d (%.1f%%)\n", successCount, float64(successCount)/float64(*numRequests)*100)
	fmt.Printf("Failed requests: %d (%.1f%%)\n", failCount, float64(failCount)/float64(*numRequests)*100)
	fmt.Printf("  - Timeouts: %d\n", timeoutCount)
	fmt.Printf("  - Socket hang ups: %d\n", socketHangUps)
	fmt.Printf("Requests per second: %.2f\n", float64(*numRequests)/totalDuration.Seconds())
	
	fmt.Println("\n--- Status Code Distribution ---")
	for code, count := range statusCodeCount {
		fmt.Printf("  %d: %d (%.1f%%)\n", code, count, float64(count)/float64(*numRequests)*100)
	}
	
	if *debugFlag && responseData != "" {
		fmt.Println("\n--- First Response Data ---")
		fmt.Printf("%s\n", responseData)
	}
}