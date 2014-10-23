{
    "port" : 8888,
    "gauth" : $$GAUTH,

    "api_names" : [],

    # Number of active containers to allow per instance
    "numlocalmax" : $$NUM_LOCALMAX,

    # Installation specific session key. Used for encryption and signing. 
    "sesskey" : "$$SESSKEY",
    
    # Users that have access to the admin tab
    "admin_users" : ["$$ADMIN_USER"],
    
    # Maximum memory allowed per docker container.
    # To be able to use `mem_limit`, the host kernel must be configured to support the same. 
    # See <http://docs.docker.io/en/latest/installation/kernel/#memory-and-swap-accounting-on-debian-ubuntu> 
    # Default 1GB containers. multiplier can be applied from user profile
    "mem_limit" : 1000000000,
    # Max 1024 cpu slices. default maximum allowed is 1/8th of total cpu slices. multiplier can be applied from user profile.
    "cpu_limit" : 128,

    # The docker image to launch
    "docker_image_pfx" : "$$DOCKER_IMAGE_PFX",
    
    "google_oauth": {
        "key": "$$CLIENT_ID", 
        "secret": "$$CLIENT_SECRET"
    },
    
    "cloud_host": {
    	"install_id": "JuliaApiBox",
    	"region": "us-east-1",
    	
    	# Enable/disable features
    	"s3": True,
    	"dynamodb": True,
    	"cloudwatch": True,
    	"autoscale": True,
    	"route53": True,

    	"autoscale_group": "julia-apibox",
    	"route53_domain": "juliabox.org",

        # Average cluster load at which to initiate scale up
    	"scale_up_at_load": 70,
    	"scale_up_policy": "addinstance",
        # Self teminate if required to scale down
        "scale_down" : False,
	    
    	"dummy" : "dummy"
    },
    "dummy" : "dummy"
}

