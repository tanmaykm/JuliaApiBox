worker_processes  2;
daemon off;
error_log logs/error.log warn;
user $$NGINX_USER $$NGINX_USER; 

events {
    worker_connections 1024;
}


http {
    resolver 8.8.8.8 8.8.4.4;
    server {
        listen 80;
        
        # To enable SSL on nginx uncomment and configure the following lines
        # We enable TLS, but not SSLv2/SSLv3 which is weak and should no longer be used and disable all weak ciphers
        # Provide full path to certificate bundle (ssl-bundle.crt) and private key (juliabox.key). Rename as appropriate.
        # All HTTP traffic is redirected to HTTPS
        
        #listen 443 default_server ssl;

        #ssl_certificate        ssl-bundle.crt;
        #ssl_certificate_key    juliabox.key;
        
        #ssl_protocols TLSv1 TLSv1.1 TLSv1.2;
        #ssl_ciphers ALL:!aNULL:!ADH:!eNULL:!LOW:!EXP:RC4+RSA:+HIGH:+MEDIUM;

        #if ($http_x_forwarded_proto = 'http') {
        #    return 302 https://$host$request_uri;
        #}

        #if ($scheme = http) {
        #    return 302 https://$host$request_uri;
        #}

        root www;

        set $SESSKEY '$$SESSKEY';
        client_max_body_size 20M;
        
        location /favicon.ico {
            include    mime.types;
        }

        location /assets/ {
            include    mime.types;
        }

# On the host, all locations will be specified explictly, i.e, with an "="
# Everything else will be proxied to the appropriate container....
# Cookie data will be used to identify the container for a session
        
        location = / {
            proxy_pass          http://localhost:8888;
            proxy_set_header    Host            $host;
            proxy_set_header    X-Real-IP       $remote_addr;
            proxy_set_header    X-Forwarded-For $remote_addr;        
        }        
        

# everything else        
        location / {
# TODO: Add request validation here
#            access_by_lua_file 'lua/validate.lua';
            
            proxy_pass          http://127.0.0.1:8888;
            proxy_set_header    Host            $host;
            proxy_set_header    X-Real-IP       $remote_addr;
            proxy_set_header    X-Forwarded-For $proxy_add_x_forwarded_for;
        }
        
    }
}

