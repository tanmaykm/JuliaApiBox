function unquote(s)
    if s:find'^"' then
        return s:sub(2,-2)
    end    
    
    return s
end


local key = ngx.var.SESSKEY
local src = unquote(ngx.var.cookie_sessname)
local digest = ngx.hmac_sha1(key, src)
local b64 = ngx.encode_base64(digest)

if b64 ~= unquote(ngx.var.cookie_sign) then
    ngx.say("Signature mismatch")
    ngx.exit(ngx.HTTP_FORBIDDEN)
end

  
