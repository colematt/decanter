import ast
from IPy import IP
import editdistance
from urlparse import urlparse
import csv


class Fingerprint():
    
    def __init__(self, label, ua, hosts, ip_dsts, const_head, lang, avg_size, outg_info, method_name, is_malicious=0):
        if label == "Background":
            self.label = label
            self.user_agent = ua
            self.hosts = hosts
            # IP destinations added
            self.ip_dsts = ip_dsts
            self.constant_header_fields = const_head
            self.language = lang
            self.avg_size = float(avg_size)
            self.outgoing_info = int(outg_info)
            self.method = method_name
            # Label indicating whether request is malicious or benign
            # Used for analysis: 0 = benign, 1 = malicious.
            # Note - isMalicious is both added to __str__ and to_csv methods.
            self.is_malicious = is_malicious
        elif label == "Browser":
            self.label = label
            self.user_agent = ua
            self.language = lang
            self.method = method_name
            self.hosts = hosts
            # IP destinations added - Added to __str__ as number of unique IP's as it becomes too large to print entirely
            self.ip_dsts = ip_dsts
            self.constant_header_fields = None
            self.avg_size = None
            self.outgoing_info = int(outg_info)
            # Label indicating whether request is malicious or benign
            # Used for analysis: 0 = benign, 1 = malicious.
            # Note - isMalicious is both added to __str__ and to_csv methods.
            self.is_malicious = is_malicious
        else:
            raise ValueError ('The label passed %s is not a "Browser" or "Background".' % (label)) 
            
    def __str__(self):
        if self.label == "Background":
            return """
            {} Application:
                    Method: {}
                    User-Agent: {}
                    Hosts: {}
                    Destination IP's: {}
                    Constant Headers: {}
                    Average Req Size: {}
                    Outgoing Info: {}
                    Is malicious: {}
            """.format(self.label, self.method, self.user_agent, self.hosts, self.ip_dsts, self.constant_header_fields, self.avg_size, self.outgoing_info, self.is_malicious=='1')    
        else:
            return """
            {} Application:
                    Method: {}
                    User-Agent: {}
                    Unique Hosts: {}
                    Unique destination IP's: {}
                    Language: {}
                    Outgoing Info: {}
                    Is malicious: {}
            """.format(self.label, self.method, self.user_agent, len(ast.literal_eval(str(self.hosts))), len(ast.literal_eval(str(self.ip_dsts))), self.language, self.outgoing_info, self.is_malicious=='1')
            
    
    def to_csv(self):
        if self.label == "Background":
            return [self.label, self.method, self.user_agent, self.hosts, self.ip_dsts, self.constant_header_fields, self.avg_size, self.outgoing_info, self.is_malicious]
        else:
            return [self.label, self.method, self.user_agent, self.hosts, self.ip_dsts, self.language, self.outgoing_info, self.is_malicious]


class FingerprintGenerator():
    
    def __init__(self):
        self.counter_req = 0
        pass

    
    def generate_fingerprint(self, method_cluster, method_name, label):
        """
            Generate the fingerprint from a set of http requests sharing the same user-agent.
            
            This method takes as input a set of HTTP requests generated by an HTTP Application.
            It analyzes each HTTP request and it extracts the features needed to generate a fingerprint of
            that HTTP application.
            
            Finally, it generates and returns a fingerprint.
            
            Parameter
            ----------------
            method_cluster : list of HTTPRequest
                All HTTP requests belonging to the same application
                
            method_name : string
                Name of the method of HTTP requests (i.e., GET or POST)
                
            label : string
                Type of the HTTP request (i.e. Browser or Background)
                
            Returns
            ----------------
            finger : Fingerprint()
                Fingerprint of the cluster of HTTP requests
        """
        
        # Temporary variables needed for fingerprint generation
        cache = []
        total_size_headers = 0
        tmp_headers = {}
        number_requests = len(method_cluster)
        self.counter_req += len(method_cluster)
        
        # Features for fingerprints
        #label = ""
        hosts = dict()
        ip_dsts = []
        constant_header_fields = []
        average_size = 0.0
        user_agent = []
        language = []
        outgoing_info = 0
        
        # TODO added for evasion analysis
        is_malicious = '1' if '1' in [m.is_malicious for m in method_cluster] else '0'
        
        # Return None if there are no request to analyze. (i.e., fingerprint does not exist)
        if not method_cluster:
            return None
        
        for http_request in method_cluster:
            
            # Add hostname
            if 'host' in http_request.header_values:
                hostname = http_request.header_values.get('host')
                clean_hostname = self._parse(hostname)
                hosts[clean_hostname] = hosts.get(clean_hostname, 0) + 1
                    
            # Add destination ip
            if http_request.dest_ip != None:
                if http_request.dest_ip not in ip_dsts:
                    ip_dsts.append(http_request.dest_ip)

            # Add user-agent
            if 'user-agent' in http_request.header_values:
                if http_request.header_values.get('user-agent') not in user_agent:
                    user_agent.append(http_request.header_values.get('user-agent'))
            else:
                # Add a default string for user-agent
                if 'None' not in user_agent:
                    user_agent.append('None')

            # Add languange
            if 'accept-language' in http_request.header_values:
                if http_request.header_values.get('accept-language') not in language:
                    language.append(http_request.header_values.get('accept-language'))
       
    
            uri_length = len(http_request.uri)
            # Case 1 : First HTTP Request
            if not cache:
                # Add first request to the cache
                cache.append(http_request)
                
                # Update the total size of the header with the size of each part of the HTTP request
                total_size_headers += uri_length
                total_size_headers += http_request.req_body_len
                for header_name in http_request.header_values.keys():
                    total_size_headers += len(header_name)
                    total_size_headers += len(http_request.header_values[header_name])
                    tmp_headers[header_name] = 1
                
                # Update outgoing information
                outgoing_info = total_size_headers
      
            # Case 2 : non-First HTTP Request
            else:
                
                # Update outgoing information
                outgoing_info = self._compute_outgoing_info(http_request, cache[0], outgoing_info, cache)
                
                # Update the total size of the header with the size of each part of the HTTP request
                total_size_headers += uri_length
                total_size_headers += http_request.req_body_len
                for header_name in http_request.header_values.keys():
                    total_size_headers += len(header_name)
                    total_size_headers += len(http_request.header_values[header_name])
                    if header_name not in tmp_headers:
                        tmp_headers[header_name] = 1
                    else:
                        tmp_headers[header_name] += 1
                        
        
        # Set Constant Header Fields
        for key, val in tmp_headers.iteritems():
            if val == number_requests:
                constant_header_fields.append(key)
                
        # Set Average Size
        average_size = total_size_headers / float(number_requests)
               
        # Generate Fingerprint for the given cluster of HTTP requests
        finger = Fingerprint(label, user_agent, hosts.items(), ip_dsts, constant_header_fields, language, average_size,
                             outgoing_info, method_name, is_malicious)
        
        return finger
        
        
    def _compute_outgoing_info(self, current_req, old_req, outgoing_info, cache):
        """
            Compute Outgoing information and update the cache.
            
            This method computes the outgoing information by comparing the current HTTP request with the
            previously analyzed HTTP request. Once the comparison is finished, the old request is removed
            from the cache, and the current request is added in the cache.
            
            Parameter
            ------------
            current_req : HTTPRequest
                HTTPRequest we are currently analyzing
            
            old_req : HTTPRequest
                HTTPRequest previously analyzed
                
            outgoing_info : int
                Current value of outgoing information
                
            cache : list of HTTPRequest
                List containing the previous HTTPRequest (i.e., old_req)
                
            Return
            ------------
            outgoing_info : int
                Update outgoing information value
        """
        # Approximation of size for POST for efficiency reasons.
        if current_req.method == "POST":
            outgoing_info += current_req.req_body_len
            return outgoing_info
        
        outgoing_info += self._levenshtein_distance(current_req.uri, old_req.uri)
        outgoing_info += current_req.req_body_len
        
        # Compute Outgoing information for each header name in the request
        for header_name in current_req.header_values.keys():
            if header_name not in old_req.header_values:
                outgoing_info += len(current_req.header_values[header_name])
            else:
                outgoing_info += self._levenshtein_distance(current_req.header_values[header_name], 
                                                      old_req.header_values[header_name] )
        
        # Update cache
        cache.pop()
        cache.append(current_req)
        return outgoing_info
    
    
    def _parse(self, hostname):
        """
            Extract the top level domain (TLD) and second level domain (SLD) from a hostname string. 
            
            E.g., Input: www.google.com ---> Output google.com
            
            If the hostname is a valid IP address, it is returned as is.
            
            Parameter
            ------------
            hostname : string
                Hostname value in the "Host" HTTP header field
                
            Return
            ------------
            top_domains  : string
                String containing second and top level domain
        """
        
        # Check if the hostname represents an IP address, if so returns its string value
        try:
            IP(hostname)
            return hostname
            
        # Otherwise parse the hostname as a URL. We need the top level domain and second level domain.
        except ValueError:
            top_domains = ".".join(hostname.split('.')[-2:])
            return top_domains
        

    def _levenshtein_distance(self, s1, s2):
        """ Compute the Levenshtein distance.
            
            Parameter
            -----------
            s1, s2 : string
                Two strings to compare
                
            Result
            -----------
            distances[-1] : int
                (Levenshtein) Edit distance
            
            """
        
        return editdistance.eval(s1, s2)


class FingerprintManager():
        
    def __init__(self):
        self.hosts_fingerprints = {}
        
    
    def store(self, host, new_fingerprint):
        if new_fingerprint is None:
            pass
        else:    
            if host not in self.hosts_fingerprints:
                self.hosts_fingerprints[host] = [new_fingerprint]
            else:
                self.hosts_fingerprints[host].append(new_fingerprint)
    
    
    def get_host_fingerprints(self, host):
        return self.hosts_fingerprints.get(host, None)
    
    
    def __str__(self):
        for host, fingerprints in self.hosts_fingerprints.iteritems():
            print "Host: " + str(host)
            for f in fingerprints:
                print str(f.__str__())
    
    
    # We can use this method to dump the fingerprints after analyzing one log.
    def write_to_file(self, filename):
        ofile = open(filename, 'wb')
        writer = csv.writer(ofile, delimiter=',', quotechar='"', quoting=csv.QUOTE_ALL)
        for host,fingerp in self.hosts_fingerprints.iteritems():
            for f in fingerp:
                input_csv = f.to_csv()
                input_csv.append(host)
                writer.writerow(input_csv)
        ofile.close()
        return
    
    # Give in input a single fingerprint and dump it into a file. IN THIS CASE WE APPEND, because in testing we get
    # fingerprints every X minutes, so they are appended as soon as they are created. 
    def write_fingerprint_to_file(self, filename, fingerprint, host):
        if fingerprint is None:
            return
        ofile = open(filename, 'a')
        writer = csv.writer(ofile, delimiter=',', quotechar='"', quoting=csv.QUOTE_ALL)
        input_csv = fingerprint.to_csv()
        input_csv.append(host)
        writer.writerow(input_csv)
        ofile.close()
        return
    
    
    # Generate a Fingerprint from a CVS row.
    def from_cvs(self, row):
        label = row[0]
        if label == "Background":
            method = row[1]
            user_agent = ast.literal_eval(row[2])
            hosts = ast.literal_eval(row[3])
            ip_dsts = ast.literal_eval(row[4])
            const_head = ast.literal_eval(row[5])
            avg_size = float(row[6])
            outgoing_info = float(row[7])
            is_malicious = row[8]
            return Fingerprint(label, user_agent, hosts, ip_dsts, const_head, None, avg_size, outgoing_info, method, is_malicious)
        else:
            method = row[1]
            user_agent = ast.literal_eval(row[2])
            hosts = ast.literal_eval(row[3])
            ip_dsts = ast.literal_eval(row[4])
            language = ast.literal_eval(row[5])
            outgoing_info = float(row[6])
            is_malicious = row[7]
            return Fingerprint(label, user_agent, hosts, ip_dsts, None, language, None, outgoing_info, method, is_malicious)
    
    
    # We can use this method to read the "trained" fingerprints.
    def read_from_file(self, filename):
        with open(filename, 'rb') as f:
            reader = csv.reader(f)
            for row in reader:
                #self.store(row[-1], self.from_cvs(row))
                self.store(filename, self.from_cvs(row))
        return
